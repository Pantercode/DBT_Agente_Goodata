"""Consultas do painel. Só leem marts agregados: nenhum KPI é recalculado aqui.

O único cálculo feito no painel é a agregação de UF para região quando o
filtro pede, e mesmo esse refaz numerador/denominador a partir das colunas
`qtd_*` e `populacao`, nunca tira média de razões.
"""

from __future__ import annotations

from dataclasses import dataclass

from consumo.dados import consultar

REGIOES = {"N": "Norte", "NE": "Nordeste", "CO": "Centro-Oeste", "SE": "Sudeste", "S": "Sul"}


@dataclass(frozen=True)
class Filtro:
    regiao: str | None = None
    uf: str | None = None

    def where(self, alias: str = "") -> tuple[str, list]:
        p = f"{alias}." if alias else ""
        clausulas, params = [], []
        if self.uf:
            clausulas.append(f"{p}uf_sigla = ?")
            params.append(self.uf)
        elif self.regiao:
            clausulas.append(f"{p}regiao_sigla = ?")
            params.append(self.regiao)
        return ("where " + " and ".join(clausulas)) if clausulas else "", params

    @property
    def rotulo(self) -> str:
        if self.uf:
            return self.uf
        if self.regiao:
            return REGIOES.get(self.regiao, self.regiao)
        return "Brasil"


def ufs() -> list[dict]:
    return consultar("select uf_sigla, regiao_sigla from publicado.agg_cobertura_uf order by uf_sigla")


def indicadores(f: Filtro) -> dict:
    if not f.uf and not f.regiao:
        return consultar("select * from publicado.agg_cobertura_brasil")[0]
    where, params = f.where()
    return consultar(
        f"""
        select
            max(dt_referencia)                                       as dt_referencia,
            sum(qtd_museus_ativos)                                   as qtd_museus_ativos,
            sum(qtd_museus_cadastrados)                              as qtd_museus_cadastrados,
            sum(qtd_pontos_memoria)                                  as qtd_pontos_memoria,
            sum(populacao)                                           as populacao,
            sum(qtd_municipios)                                      as qtd_municipios,
            sum(qtd_municipios_com_museu)                            as qtd_municipios_com_museu,
            sum(qtd_municipios_com_museu) * 1.0 / sum(qtd_municipios) as pct_municipios_com_museu,
            sum(populacao_sem_museu)                                 as populacao_sem_museu,
            sum(populacao_sem_museu) * 1.0 / sum(populacao)          as pct_populacao_sem_museu,
            sum(qtd_museus_ativos) * 100000.0 / sum(populacao)       as museus_por_100k_hab,
            sum(indice_gestao_medio * qtd_museus_ativos) / sum(qtd_museus_ativos) as indice_gestao_medio
        from publicado.agg_cobertura_uf
        cross join (select max(dt_referencia) as dt_referencia from publicado.agg_cobertura_brasil)
        {where}
    """,
        params,
    )[0]


def cobertura_uf(f: Filtro) -> list[dict]:
    where, params = f.where()
    return consultar(f"select * from publicado.agg_cobertura_uf {where} order by museus_por_100k_hab desc", params)


def todas_ufs() -> list[dict]:
    return consultar("select * from publicado.agg_cobertura_uf order by museus_por_100k_hab desc")


def cobertura_por_porte(f: Filtro) -> list[dict]:
    where, params = f.where()
    return consultar(
        f"""
        select faixa_populacional, classe_cobertura, count(*) as qtd_municipios, sum(populacao) as populacao
        from publicado.agg_cobertura_municipio
        {where}
        group by 1, 2
        order by 1, 2
    """,
        params,
    )


def maiores_municipios_sem_museu(f: Filtro, limite: int = 12) -> list[dict]:
    where, params = f.where()
    where = (where + " and " if where else "where ") + "not tem_museu_ativo"
    return consultar(
        f"""
        select municipio_rotulo, populacao
        from publicado.agg_cobertura_municipio
        {where}
        order by populacao desc
        limit {int(limite)}
    """,
        params,
    )


def aberturas_por_decada(f: Filtro) -> list[dict]:
    where = ""
    params: list = []
    if f.regiao and not f.uf:
        where, params = "where regiao_sigla = ?", [f.regiao]
    return consultar(
        f"""
        select decada_abertura, natureza_administrativa, sum(qtd_museus) as qtd_museus
        from publicado.agg_aberturas_por_decada
        {where}
        group by 1, 2
        order by 1
    """,
        params,
    )


def gestao_criterios(f: Filtro) -> list[dict]:
    where, params = f.where()
    # Recorte por UF exige a OBT (agg_gestao_por_perfil é nacional).
    return consultar(
        f"""
        select
            natureza_administrativa,
            count(*) as qtd,
            avg(case when gestao.plano_museologico then 1.0 else 0.0 end)  as plano_museologico,
            avg(case when gestao.regimento_interno then 1.0 else 0.0 end)  as regimento_interno,
            avg(case when gestao.documentacao_acervo then 1.0 else 0.0 end) as documentacao_acervo,
            avg(case when gestao.politica_aquisicao then 1.0 else 0.0 end) as politica_aquisicao,
            avg(case when gestao.politica_descarte then 1.0 else 0.0 end)  as politica_descarte,
            avg(case when equipe.pessoas_trabalham > 0 then 1.0 else 0.0 end) as equipe_propria
        from publicado.obt_museus
        {(where + " and ") if where else "where "} is_aberto and natureza_administrativa <> 'Não informada'
        group by 1
        order by 1
    """,
        params,
    )


def faixas_gestao(f: Filtro) -> list[dict]:
    where, params = f.where()
    return consultar(
        f"""
        select gestao.faixa as faixa, natureza_administrativa, count(*) as qtd
        from publicado.obt_museus
        {(where + " and ") if where else "where "} is_aberto and natureza_administrativa <> 'Não informada'
        group by 1, 2
    """,
        params,
    )


def recursos_acessibilidade(f: Filtro) -> list[dict]:
    where, params = f.where()
    # agg_recursos_acessibilidade não tem região; vem da tabela de UF. O
    # denominador é o total de museus ativos do recorte, não a soma por recurso.
    return consultar(
        f"""
        with base as (
            select r.*, u.regiao_sigla
            from publicado.agg_recursos_acessibilidade r
            join publicado.agg_cobertura_uf u using (uf_sigla)
        ),
        recorte as (select * from base {where}),
        denominador as (
            select sum(qtd_museus_ativos) as total
            from publicado.agg_cobertura_uf
            where uf_sigla in (select uf_sigla from recorte)
        )
        select dimensao, recurso,
               sum(qtd_museus_com_recurso) as qtd,
               sum(qtd_museus_com_recurso) * 1.0 / max(d.total) as pct
        from recorte cross join denominador d
        group by 1, 2
        order by pct desc
    """,
        params,
    )


def acessibilidade_dimensoes(f: Filtro) -> list[dict]:
    where, params = f.where()
    return consultar(
        f"""
        select acessibilidade.dimensoes_atendidas as dimensoes, count(*) as qtd
        from publicado.obt_museus
        {(where + " and ") if where else "where "} is_aberto
        group by 1 order by 1
    """,
        params,
    )


def completude(f: Filtro) -> list[dict]:
    where, params = f.where()
    return consultar(
        f"""
        with base as (
            select c.uf_sigla, c.campo, c.pct_preenchido, c.qtd_museus, c.qtd_preenchidos, u.regiao_sigla
            from publicado.mart_completude_cadastro c
            join publicado.agg_cobertura_uf u using (uf_sigla)
        )
        select * from base {where}
        order by uf_sigla
    """,
        params,
    )


def ultimos_testes() -> list[dict]:
    return consultar("""
        select tipo, nome, modelo_alvo, status, bloqueante, falhas, tempo_s
        from publicado.qualidade_testes
        where invocation_id = (select invocation_id from publicado.qualidade_testes order by executado_em desc limit 1)
          and tipo in ('test', 'unit_test')
        order by bloqueante desc, nome
    """)


def historico_testes() -> list[dict]:
    return consultar("""
        select invocation_id, min(executado_em) as executado_em,
               count(*) filter (where status = 'pass') as aprovados,
               count(*) filter (where status in ('fail', 'error')) as reprovados,
               count(*) filter (where status = 'warn') as avisos
        from publicado.qualidade_testes
        where tipo in ('test', 'unit_test')
        group by 1 order by 2
    """)


def museus_no_mapa(f: Filtro) -> list[dict]:
    where, params = f.where()
    return consultar(
        f"""
        select nome_museu, municipio_nome, uf_sigla, natureza_administrativa,
               localizacao.latitude as lat, localizacao.longitude as lon
        from publicado.obt_museus
        {(where + " and ") if where else "where "} is_aberto and localizacao.latitude is not null
    """,
        params,
    )


def participacao_regioes() -> list[dict]:
    """% da população e % dos museus ativos de cada região, sobre o total nacional."""
    return consultar("""
        select
            regiao_sigla,
            max(regiao_nome) as regiao_nome,
            sum(populacao) * 1.0 / (select sum(populacao) from publicado.agg_cobertura_uf) as pct_populacao,
            sum(qtd_museus_ativos) * 1.0 / (select sum(qtd_museus_ativos) from publicado.agg_cobertura_uf) as pct_museus
        from publicado.agg_cobertura_uf
        group by regiao_sigla
    """)


def marcos_linha_do_tempo(f: Filtro) -> dict:
    """Dados para a linha do tempo da capa: década com mais aberturas e o museu ativo mais antigo."""
    where, params = f.where()
    base = f"from publicado.obt_museus {(where + ' and ') if where else 'where '} ano_abertura between 1800 and 2026"
    pico = consultar(
        f"""
        select cast(floor(ano_abertura / 10) * 10 as integer) as decada, count(*) as qtd
        {base} group by 1 order by 2 desc limit 1
    """,
        params,
    )
    antigo = consultar(
        f"""
        select nome_museu, municipio_nome, uf_sigla, ano_abertura
        {base} and is_aberto order by ano_abertura, nome_museu limit 1
    """,
        params,
    )
    ultima_decada = consultar(f"select count(*) as qtd {base} and ano_abertura >= 2016", params)
    return {
        "pico": pico[0] if pico else None,
        "mais_antigo": antigo[0] if antigo else None,
        "ultimos_dez_anos": ultima_decada[0]["qtd"] if ultima_decada else 0,
    }


def saude_coleta() -> list[dict]:
    return consultar("""
        select fonte, dt, status, motivo_quarentena, registros_lidos, regua_volume, pct_sem_uf,
               is_particao_em_uso, dt_em_uso, is_mais_nova_que_a_publicada
        from publicado.mart_saude_coleta
        order by dt desc, fonte
    """)


def quarentena_pendente() -> dict | None:
    """A partição mais nova que ficou de fora, se houver (o painel avisa no cabeçalho)."""
    linhas = consultar("""
        select fonte, dt, motivo_quarentena, dt_em_uso
        from publicado.mart_saude_coleta
        where status = 'quarentena' and is_mais_nova_que_a_publicada
        order by dt desc limit 1
    """)
    return linhas[0] if linhas else None
