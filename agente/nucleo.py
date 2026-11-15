"""Loop do agente: Gemini com function calling manual e resposta em streaming.

`eventos()` é um gerador. Cada coisa que acontece vira um evento que o painel
recebe ao vivo (NDJSON):

    {"tipo": "inicio",   "modelo": ...}
    {"tipo": "passo",    "ferramenta": ..., "argumentos": ..., "estado": "rodando"}
    {"tipo": "passo",    ..., "estado": "ok" | "erro", "sql": ..., "duracao_ms": ...}
    {"tipo": "grafico",  "id": ..., "titulo": ..., "figura": {plotly json}}
    {"tipo": "texto",    "delta": "..."}          (pedaços da resposta, na ordem)
    {"tipo": "fim",      "texto": ..., "sugestoes": [...], "modelo": ..., "tokens": ...}
    {"tipo": "erro",     "mensagem": ...}

`perguntar()` consome o gerador e devolve a Resposta inteira (CLI, testes,
avaliação).

Por que loop manual e não o `automatic_function_calling` do SDK:
  - cada ferramenta vira evento e entra no rastro ("como cheguei nesse número");
  - teto de iterações controlado aqui;
  - erro de ferramenta volta para o modelo se corrigir, sem quebrar a conversa;
  - artefatos (figuras) saem da ferramenta direto para o usuário, sem passar
    pelo contexto do modelo.
"""

from __future__ import annotations

import logging
import os
import re
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from agente import ferramentas, memoria

log = logging.getLogger(__name__)

PROMPT_SISTEMA = (Path(__file__).parent / "prompts" / "sistema.md").read_text(encoding="utf-8")
MODELO_PADRAO = "gemini-3.8-flash"
# Se o modelo principal estiver sobrecarregado (503) ou sem cota (429, comum no
# free tier), cai para o próximo. A troca fica registrada no evento `fim`.
MODELOS_RESERVA = ("gemini-3.5-flash", "gemini-3.1-flash-lite")
MAX_ITERACOES = 8
# Tempo máximo esperando um modelo começar a responder. Curto e sem retry no
# mesmo modelo: no free tier, modelo lento quase sempre é modelo sobrecarregado,
# e é mais rápido trocar do que esperar (antes: 45 s x 2 tentativas por modelo,
# o que deixava a tela minutos em "Pensando").
TIMEOUT_MS = 25_000
# Modelo que deu 429/timeout fica de fora por um tempo; as próximas perguntas
# vão direto para um que está respondendo.
RESFRIAMENTO_S = 180
_resfriando: dict[str, float] = {}

# O prompt pede que a resposta termine com um bloco de sugestões; ele é
# separado do texto e vira botões no chat.
_SUGESTOES = re.compile(
    r"(?:\n[ \t]*-{3,}[ \t]*)?\n[ \t]*\**Próximas perguntas:?\**[ \t]*\n(?P<itens>(?:[ \t]*[-*][ \t]+.+\n?)+)\s*$",
    re.IGNORECASE,
)


@dataclass
class Passo:
    ferramenta: str
    argumentos: dict
    resumo: str
    sql: str | None = None
    erro: bool = False
    duracao_ms: int = 0


@dataclass
class Resposta:
    texto: str
    passos: list[Passo] = field(default_factory=list)
    graficos: list[dict] = field(default_factory=list)
    sugestoes: list[str] = field(default_factory=list)
    modelo: str = ""
    iteracoes: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    interrompida: bool = False

    def para_dict(self) -> dict:
        return asdict(self)


class AgenteIndisponivel(RuntimeError):
    pass


def _cliente() -> genai.Client:
    chave = os.environ.get("GEMINI_API_KEY")
    if not chave:
        raise AgenteIndisponivel("GEMINI_API_KEY não configurada. Defina no .env (local) ou nas variáveis da Vercel.")
    return genai.Client(
        api_key=chave,
        http_options=types.HttpOptions(timeout=TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=1)),
    )


def _configuracao(contexto: str | None, pergunta: str = "") -> types.GenerateContentConfig:
    declaracoes = [
        types.FunctionDeclaration(name=d["name"], description=d["description"], parameters_json_schema=d["parameters"])
        for d in ferramentas.DECLARACOES
    ]
    # Catálogo + exemplos verificados parecidos com a pergunta (agente/memoria.py).
    sistema = PROMPT_SISTEMA + "\n\n" + memoria.bloco_para_prompt(pergunta)
    if contexto:
        # Contexto da tela (recorte do filtro). Vai no fim do prompt de sistema,
        # não na pergunta, para o modelo tratar como situação e não como pedido.
        sistema += f"\n\nContexto da tela: {contexto}"
    return types.GenerateContentConfig(
        system_instruction=sistema,
        tools=[types.Tool(function_declarations=declaracoes)],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0.2,
    )


def _historico_para_contents(historico: list[dict]) -> list[types.Content]:
    """Histórico vem do navegador como [{papel: usuario|agente, texto}]. Só texto: o
    rastro de ferramentas de turnos anteriores não volta (economiza contexto, e os
    números citados já estão no texto)."""
    contents = []
    for msg in historico[-10:]:
        papel = "user" if msg.get("papel") == "usuario" else "model"
        contents.append(types.Content(role=papel, parts=[types.Part.from_text(text=str(msg.get("texto", ""))[:4000])]))
    return contents


def _ordenar_por_disponibilidade(modelos: list[str]) -> list[str]:
    """Modelos em resfriamento vão para o fim da fila (continuam como último recurso)."""
    agora = time.monotonic()
    livres = [m for m in modelos if _resfriando.get(m, 0) <= agora]
    return livres + [m for m in modelos if m not in livres]


def _abrir_stream(cliente: genai.Client, modelos: list[str], contents, config):
    """Gerador: tenta os modelos em ordem e devolve (modelo, primeiro_pedaco, stream).

    Cada tentativa que falha vira um evento `aviso`, para a tela mostrar o que
    está acontecendo em vez de ficar parada. O erro de cota/sobrecarga só aparece
    ao ler o primeiro pedaço, por isso ele é lido aqui.
    429, 5xx, 404 e timeout passam para o próximo modelo e colocam o atual em
    resfriamento. Outros 4xx não melhoram trocando de modelo."""
    ultimo_erro: Exception | None = None
    so_cota = True
    fila = _ordenar_por_disponibilidade(modelos)
    for i, modelo in enumerate(fila):
        try:
            stream = cliente.models.generate_content_stream(model=modelo, contents=contents, config=config)
            primeiro = next(iter(stream), None)
            _resfriando.pop(modelo, None)
            return modelo, primeiro, stream
        except genai_errors.ClientError as exc:
            if exc.code not in (404, 429):
                raise AgenteIndisponivel(f"A API Gemini recusou a requisição ({exc.code}).") from exc
            so_cota = so_cota and exc.code == 429
            motivo = "sem cota no momento" if exc.code == 429 else "indisponível para esta chave"
            ultimo_erro = exc
        except Exception as exc:  # 5xx, timeout do transporte HTTP (httpx levanta tipos próprios), rede
            so_cota = False
            motivo = "lento ou sobrecarregado"
            ultimo_erro = exc
        _resfriando[modelo] = time.monotonic() + RESFRIAMENTO_S
        log.warning("modelo %s %s (%s), tentando o próximo", modelo, motivo, type(ultimo_erro).__name__)
        proximo = fila[i + 1] if i + 1 < len(fila) else None
        if proximo:
            yield {"tipo": "aviso", "mensagem": f"{modelo} {motivo}; tentando {proximo}"}
    if so_cota:
        raise AgenteIndisponivel(
            "Limite de uso da API Gemini atingido em todos os modelos. Tente de novo em um minuto."
        ) from ultimo_erro
    raise AgenteIndisponivel(
        "A API Gemini está sobrecarregada no momento. Tente de novo em instantes."
    ) from ultimo_erro


def separar_sugestoes(texto: str) -> tuple[str, list[str]]:
    m = _SUGESTOES.search(texto)
    if not m:
        return texto.strip(), []
    itens = [re.sub(r"^\s*[-*]\s*", "", linha).strip() for linha in m.group("itens").strip().splitlines()]
    return texto[: m.start()].rstrip(), [i for i in itens if i][:3]


def eventos(
    pergunta: str, historico: list[dict] | None = None, contexto: str | None = None, modelo: str | None = None
) -> Iterator[dict]:
    principal = modelo or os.environ.get("GEMINI_MODEL", MODELO_PADRAO)
    modelos = list(dict.fromkeys([principal, *MODELOS_RESERVA]))
    try:
        cliente = _cliente()
    except AgenteIndisponivel as exc:
        yield {"tipo": "erro", "mensagem": str(exc)}
        return
    config = _configuracao(contexto, pergunta)
    contents = _historico_para_contents(historico or [])
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=pergunta)]))

    tokens_entrada = tokens_saida = 0
    usado = principal
    texto_total = ""

    for iteracao in range(1, MAX_ITERACOES + 1):
        try:
            usado, primeiro, stream = yield from _abrir_stream(cliente, modelos, contents, config)
        except AgenteIndisponivel as exc:
            yield {"tipo": "erro", "mensagem": str(exc)}
            return
        if iteracao == 1:
            yield {"tipo": "inicio", "modelo": usado}
        # Uma vez na reserva, fica nela até o fim: trocar de modelo no meio do
        # loop de ferramentas confunde o raciocínio.
        modelos = modelos[modelos.index(usado) :]

        partes: list[types.Part] = []
        chamadas: list[types.FunctionCall] = []
        texto_turno = ""
        entrada = saida = 0

        def pedacos(primeiro=primeiro, stream=stream):
            if primeiro is not None:
                yield primeiro
            yield from stream

        try:
            for pedaco in pedacos():
                if pedaco.usage_metadata:
                    # o último pedaço traz o total do turno
                    entrada = pedaco.usage_metadata.prompt_token_count or 0
                    saida = pedaco.usage_metadata.candidates_token_count or 0
                if not pedaco.candidates or not pedaco.candidates[0].content:
                    continue
                for parte in pedaco.candidates[0].content.parts or []:
                    # A parte vai inteira para o histórico: no Gemini 3 ela carrega
                    # a thought_signature que a próxima chamada precisa receber de volta.
                    partes.append(parte)
                    if parte.function_call:
                        chamadas.append(parte.function_call)
                    elif parte.text and not parte.thought:
                        texto_turno += parte.text
                        yield {"tipo": "texto", "delta": parte.text}
        except Exception as exc:  # queda no meio do stream: o usuário vê o erro, não um 500
            yield {
                "tipo": "erro",
                "mensagem": f"A conexão com o modelo caiu no meio da resposta ({type(exc).__name__}).",
            }
            return
        tokens_entrada += entrada
        tokens_saida += saida
        texto_total += texto_turno

        if not partes:
            yield {"tipo": "erro", "mensagem": "O modelo não devolveu resposta."}
            return
        contents.append(types.Content(role="model", parts=partes))

        if not chamadas:
            texto, sugestoes = separar_sugestoes(texto_total)
            yield {
                "tipo": "fim",
                "texto": texto,
                "sugestoes": sugestoes,
                "modelo": usado,
                "iteracoes": iteracao,
                "tokens": tokens_entrada + tokens_saida,
            }
            return

        respostas = []
        for chamada in chamadas:
            argumentos = dict(chamada.args or {})
            yield {"tipo": "passo", "ferramenta": chamada.name, "argumentos": argumentos, "estado": "rodando"}
            inicio = time.monotonic()
            resultado = ferramentas.executar(chamada.name, argumentos)
            figura = resultado.pop("_figura", None)
            duracao = int((time.monotonic() - inicio) * 1000)
            yield {
                "tipo": "passo",
                "ferramenta": chamada.name,
                "argumentos": argumentos,
                "estado": "erro" if "erro" in resultado else "ok",
                "sql": resultado.get("sql_executado"),
                "resumo": ferramentas.resumo_para_log(resultado),
                "duracao_ms": duracao,
            }
            if figura:
                yield {
                    "tipo": "grafico",
                    "id": resultado.get("grafico_id"),
                    "titulo": argumentos.get("titulo"),
                    "figura": figura,
                }
            log.info("ferramenta %s %s (%sms)", chamada.name, argumentos, duracao)
            respostas.append(types.Part.from_function_response(name=chamada.name, response={"resultado": resultado}))
        # Todos os resultados de um turno vão juntos, numa mensagem só.
        contents.append(types.Content(role="user", parts=respostas))

    texto, sugestoes = separar_sugestoes(texto_total)
    yield {
        "tipo": "fim",
        "texto": (texto + "\n\n" if texto else "")
        + "Parei antes de concluir: a pergunta exigiu mais passos do que o limite. Tente algo mais específico.",
        "sugestoes": sugestoes,
        "modelo": usado,
        "iteracoes": MAX_ITERACOES,
        "tokens": tokens_entrada + tokens_saida,
        "interrompida": True,
    }


def perguntar(
    pergunta: str, historico: list[dict] | None = None, contexto: str | None = None, modelo: str | None = None
) -> Resposta:
    """Versão síncrona: consome os eventos e devolve a resposta inteira."""
    r = Resposta(texto="")
    for ev in eventos(pergunta, historico, contexto, modelo):
        if ev["tipo"] == "erro":
            raise AgenteIndisponivel(ev["mensagem"])
        if ev["tipo"] == "passo" and ev["estado"] != "rodando":
            r.passos.append(
                Passo(
                    ev["ferramenta"],
                    ev["argumentos"],
                    ev.get("resumo", ""),
                    ev.get("sql"),
                    ev["estado"] == "erro",
                    ev.get("duracao_ms", 0),
                )
            )
        elif ev["tipo"] == "grafico":
            r.graficos.append({"id": ev["id"], "titulo": ev["titulo"]})
        elif ev["tipo"] == "fim":
            r.texto, r.sugestoes, r.modelo = ev["texto"], ev["sugestoes"], ev["modelo"]
            r.iteracoes, r.tokens_saida = ev["iteracoes"], ev["tokens"]
            r.interrompida = ev.get("interrompida", False)
    return r
