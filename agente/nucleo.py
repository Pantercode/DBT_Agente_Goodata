"""Loop do agente: Gemini com function calling manual.

Por que manual e não o `automatic_function_calling` do SDK:
  - cada chamada de ferramenta entra no `rastro`, que o painel mostra
    ("como cheguei nesse número": ferramenta, argumentos, SQL executado);
  - teto de iterações e de chamadas por turno, controlados aqui;
  - erro de ferramenta volta como resultado para o modelo se corrigir, em vez
    de levantar exceção dentro do SDK.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from agente import ferramentas

log = logging.getLogger(__name__)

PROMPT_SISTEMA = (Path(__file__).parent / "prompts" / "sistema.md").read_text(encoding="utf-8")
MODELO_PADRAO = "gemini-3.8-flash"
# Se o modelo principal estiver sobrecarregado (503, comum no free tier), cai
# para o próximo. A troca fica registrada em Resposta.modelo.
MODELOS_RESERVA = ("gemini-3.5-flash", "gemini-3.1-flash-lite")
MAX_ITERACOES = 8
# Sem isso o SDK tenta de novo por vários minutos e a função da Vercel morre antes.
TIMEOUT_MS = 45_000


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
        http_options=types.HttpOptions(timeout=TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=2)),
    )


def _configuracao() -> types.GenerateContentConfig:
    declaracoes = [
        types.FunctionDeclaration(name=d["name"], description=d["description"], parameters_json_schema=d["parameters"])
        for d in ferramentas.DECLARACOES
    ]
    return types.GenerateContentConfig(
        system_instruction=PROMPT_SISTEMA,
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


def _gerar(cliente: genai.Client, modelos: list[str], contents, config) -> tuple[types.GenerateContentResponse, str]:
    """Tenta cada modelo da lista em ordem.

    503/504/timeout e 429 passam para o próximo: no free tier a cota é por
    modelo, então estourar a do principal não impede a reserva de responder.
    404 (modelo aposentado para a chave) também. Outros 4xx (chave inválida,
    requisição malformada) não melhoram trocando de modelo."""
    ultimo_erro: Exception | None = None
    so_cota = True
    for modelo in modelos:
        try:
            return cliente.models.generate_content(model=modelo, contents=contents, config=config), modelo
        except genai_errors.ClientError as exc:
            if exc.code not in (404, 429):
                raise AgenteIndisponivel(f"A API Gemini recusou a requisição ({exc.code}).") from exc
            so_cota = so_cota and exc.code == 429
            log.warning("modelo %s recusou (%s), tentando o próximo", modelo, exc.code)
            ultimo_erro = exc
        except (genai_errors.ServerError, TimeoutError, OSError) as exc:
            so_cota = False
            log.warning("modelo %s indisponível (%s), tentando o próximo", modelo, exc)
            ultimo_erro = exc
    if so_cota:
        raise AgenteIndisponivel(
            "Limite de uso da API Gemini atingido em todos os modelos. Tente de novo em um minuto."
        ) from ultimo_erro
    raise AgenteIndisponivel(
        "A API Gemini está sobrecarregada no momento. Tente de novo em instantes."
    ) from ultimo_erro


def perguntar(pergunta: str, historico: list[dict] | None = None, modelo: str | None = None) -> Resposta:
    principal = modelo or os.environ.get("GEMINI_MODEL", MODELO_PADRAO)
    modelos = list(dict.fromkeys([principal, *MODELOS_RESERVA]))
    cliente = _cliente()
    config = _configuracao()
    contents = _historico_para_contents(historico or [])
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=pergunta)]))
    resposta = Resposta(texto="", modelo=principal)

    for iteracao in range(1, MAX_ITERACOES + 1):
        resposta.iteracoes = iteracao
        r, usado = _gerar(cliente, modelos, contents, config)
        # Uma vez que caiu para a reserva, fica nela até o fim do turno: trocar de
        # modelo no meio do loop de ferramentas confunde o raciocínio.
        modelos = modelos[modelos.index(usado) :]
        resposta.modelo = usado

        if r.usage_metadata:
            resposta.tokens_entrada += r.usage_metadata.prompt_token_count or 0
            resposta.tokens_saida += r.usage_metadata.candidates_token_count or 0

        if not r.candidates or not r.candidates[0].content:
            motivo = r.candidates[0].finish_reason if r.candidates else "sem candidato"
            resposta.texto = f"O modelo não devolveu resposta ({motivo})."
            return resposta

        contents.append(r.candidates[0].content)
        chamadas = r.function_calls or []
        if not chamadas:
            resposta.texto = (r.text or "").strip()
            return resposta

        partes = []
        for chamada in chamadas:
            argumentos = dict(chamada.args or {})
            inicio = time.monotonic()
            resultado = ferramentas.executar(chamada.name, argumentos)
            passo = Passo(
                ferramenta=chamada.name,
                argumentos=argumentos,
                resumo=ferramentas.resumo_para_log(resultado),
                sql=resultado.get("sql_executado"),
                erro="erro" in resultado,
                duracao_ms=int((time.monotonic() - inicio) * 1000),
            )
            resposta.passos.append(passo)
            log.info("ferramenta %s %s -> %s", chamada.name, argumentos, passo.resumo[:120])
            partes.append(types.Part.from_function_response(name=chamada.name, response={"resultado": resultado}))
        # Todos os resultados de um turno vão juntos, numa mensagem só.
        contents.append(types.Content(role="user", parts=partes))

    resposta.interrompida = True
    resposta.texto = (
        "Parei antes de concluir: a pergunta exigiu mais passos do que o limite configurado. "
        "Tente uma pergunta mais específica."
    )
    return resposta
