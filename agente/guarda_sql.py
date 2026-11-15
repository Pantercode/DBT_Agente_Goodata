"""Validação do SQL gerado pelo modelo antes de executar.

Defesa em camadas. Esta é a segunda; a primeira é a própria conexão
(consumo.dados), que só tem `publicado` e não acessa disco nem rede.

Aqui, pela AST (sqlglot, dialeto duckdb):
  1. exatamente um statement;
  2. tem que ser SELECT (ou WITH ... SELECT); nada de DDL, DML, PRAGMA, SET, COPY, ATTACH;
  3. toda tabela referenciada precisa estar em `publicado` e existir;
  4. nenhuma table function (read_csv, read_parquet, glob...): só tabelas;
  5. LIMIT obrigatório, com teto. Se não vier, é injetado.

Regex em cima de SQL não funciona (comentários, strings, CTEs com o mesmo nome
de uma tabela). Por isso a AST.
"""

from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

LIMITE_PADRAO = 200
LIMITE_MAXIMO = 1000
SCHEMA_PERMITIDO = "publicado"


class SQLRecusado(ValueError):
    """O SQL não passou na validação. A mensagem volta para o modelo corrigir."""


@dataclass(frozen=True)
class SQLValidado:
    sql: str
    tabelas: tuple[str, ...]
    limite: int


def validar(sql: str, tabelas_existentes: set[str]) -> SQLValidado:
    try:
        statements = [s for s in sqlglot.parse(sql, dialect="duckdb") if s is not None]
    except sqlglot.errors.ParseError as exc:
        raise SQLRecusado(f"SQL inválido: {exc.errors[0]['description'] if exc.errors else exc}") from exc

    if len(statements) != 1:
        raise SQLRecusado("Envie exatamente uma consulta (um único SELECT).")
    arvore = statements[0]

    if not isinstance(arvore, exp.Query):
        raise SQLRecusado(f"Só consultas SELECT são permitidas; recebi {arvore.key.upper()}.")

    proibidos = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Drop,
        exp.Create,
        exp.Alter,
        exp.Command,
        exp.Copy,
        exp.Set,
        exp.Pragma,
        exp.Attach,
        exp.Detach,
        exp.Use,
    )
    if any(arvore.find_all(*proibidos)):
        raise SQLRecusado("A consulta contém uma operação que não é leitura.")

    if any(arvore.find_all(exp.Anonymous)) or any(isinstance(t.this, exp.Func) for t in arvore.find_all(exp.Table)):
        # exp.Anonymous pega funções desconhecidas; mais seguro tratar table functions pela posição no FROM.
        for tabela in arvore.find_all(exp.Table):
            if isinstance(tabela.this, exp.Func):
                raise SQLRecusado("Funções de tabela (read_csv, read_parquet, glob...) não são permitidas.")

    nomes_cte = {cte.alias_or_name for cte in arvore.find_all(exp.CTE)}
    usadas = []
    for tabela in arvore.find_all(exp.Table):
        if tabela.name in nomes_cte and not tabela.db:
            continue
        schema = tabela.db or SCHEMA_PERMITIDO
        if schema != SCHEMA_PERMITIDO or tabela.catalog:
            raise SQLRecusado(f"Só o schema `publicado` pode ser consultado (recebi `{tabela.sql()}`).")
        if tabela.name not in tabelas_existentes:
            raise SQLRecusado(
                f"A tabela `{tabela.name}` não existe em `publicado`. Disponíveis: {', '.join(sorted(tabelas_existentes))}."
            )
        # Normaliza para nome qualificado: a conexão não tem search_path para `publicado`.
        tabela.set("db", exp.to_identifier(SCHEMA_PERMITIDO))
        usadas.append(tabela.name)

    limite = arvore.args.get("limit")
    valor = None
    if limite is not None:
        try:
            valor = int(limite.expression.this)
        except (AttributeError, TypeError, ValueError):
            valor = None
    if valor is None or valor > LIMITE_MAXIMO:
        valor = min(valor or LIMITE_PADRAO, LIMITE_MAXIMO)
        arvore = arvore.limit(valor)

    return SQLValidado(sql=arvore.sql(dialect="duckdb"), tabelas=tuple(dict.fromkeys(usadas)), limite=valor)
