from __future__ import annotations

import logging

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

log = logging.getLogger(__name__)

# O servidor do Ibram é lento em horário comercial (páginas de 48 itens levam
# de 5 a 15 s). Timeout de leitura generoso, conexão curta.
TIMEOUT = httpx.Timeout(connect=15.0, read=240.0, write=30.0, pool=30.0)

USER_AGENT = "museus-analytics/1.0 (+https://github.com/MarcellOliveira_dux)"


def novo_cliente() -> httpx.Client:
    return httpx.Client(
        timeout=TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )


class RespostaInvalida(RuntimeError):
    """A API respondeu 200, mas com corpo que não é JSON (acontece sob carga)."""


_ERROS_TRANSITORIOS = (httpx.TransportError, httpx.HTTPStatusError, RespostaInvalida)


@retry(
    retry=retry_if_exception_type(_ERROS_TRANSITORIOS),
    stop=stop_after_attempt(6),
    wait=wait_exponential_jitter(initial=2, max=60),
    before_sleep=before_sleep_log(log, logging.WARNING),
    reraise=True,
)
def get_json(cliente: httpx.Client, url: str, params: dict | None = None) -> tuple[object, httpx.Headers]:
    resp = cliente.get(url, params=params)
    if resp.status_code in (429, 500, 502, 503, 504):
        resp.raise_for_status()
    if resp.status_code >= 400:
        # 4xx que não seja 429 não melhora com retry: falha logo.
        raise httpx.HTTPError(f"{resp.status_code} em {resp.url}: {resp.text[:200]}")
    try:
        return resp.json(), resp.headers
    except ValueError as exc:
        raise RespostaInvalida(f"corpo não-JSON em {resp.url}") from exc
