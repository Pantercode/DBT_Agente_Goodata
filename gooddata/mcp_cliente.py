"""Cliente mínimo do servidor MCP do GoodData (streamable HTTP, JSON-RPC).

    python -m gooddata.mcp_cliente ferramentas          # lista as ferramentas do servidor
    python -m gooddata.mcp_cliente chamar NOME '{json}' # chama uma ferramenta

É o mesmo servidor que o Claude Code usa pelo .mcp.json. Ter um cliente em
código serve para automatizar (CI, scripts) e para depurar o que o MCP
devolve sem depender de uma sessão interativa.
"""

from __future__ import annotations

import json
import os
import sys
from itertools import count
from pathlib import Path

import httpx
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent


class ClienteMCP:
    def __init__(self) -> None:
        load_dotenv(RAIZ / ".env")
        host = os.environ["GOODDATA_HOST"].rstrip("/")
        ws = os.environ["GOODDATA_WORKSPACE"]
        self.url = f"{host}/api/v1/actions/workspaces/{ws}/ai/mcp"
        self.http = httpx.Client(
            timeout=180,
            headers={
                "Authorization": f"Bearer {os.environ['GOODDATA_TOKEN']}",
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )
        self._ids = count(1)
        self.sessao: str | None = None
        self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "museus-br", "version": "1.0"},
            },
        )
        self._notificar("notifications/initialized")

    def _cabecalhos(self) -> dict:
        return {"Mcp-Session-Id": self.sessao} if self.sessao else {}

    @staticmethod
    def _ler(resp: httpx.Response) -> dict:
        if "text/event-stream" in resp.headers.get("content-type", ""):
            # pega o último evento `data:` com resposta JSON-RPC
            dados = [ln[5:].strip() for ln in resp.text.splitlines() if ln.startswith("data:")]
            return json.loads(dados[-1]) if dados else {}
        return resp.json()

    def _rpc(self, metodo: str, params: dict | None = None) -> dict:
        r = self.http.post(
            self.url,
            headers=self._cabecalhos(),
            json={"jsonrpc": "2.0", "id": next(self._ids), "method": metodo, "params": params or {}},
        )
        r.raise_for_status()
        self.sessao = r.headers.get("mcp-session-id", self.sessao)
        corpo = self._ler(r)
        if "error" in corpo:
            raise RuntimeError(f"{metodo}: {corpo['error']}")
        return corpo.get("result", {})

    def _notificar(self, metodo: str) -> None:
        self.http.post(self.url, headers=self._cabecalhos(), json={"jsonrpc": "2.0", "method": metodo})

    def ferramentas(self) -> list[dict]:
        return self._rpc("tools/list").get("tools", [])

    def chamar(self, nome: str, argumentos: dict) -> dict:
        return self._rpc("tools/call", {"name": nome, "arguments": argumentos})


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    c = ClienteMCP()
    if len(sys.argv) > 1 and sys.argv[1] == "chamar":
        print(
            json.dumps(
                c.chamar(sys.argv[2], json.loads(sys.argv[3] if len(sys.argv) > 3 else "{}")),
                ensure_ascii=False,
                indent=2,
            )[:6000]
        )
        return 0
    for f in c.ferramentas():
        props = list((f.get("inputSchema") or {}).get("properties", {}))
        print(f"- {f['name']}: {(f.get('description') or '').strip().splitlines()[0][:150]}\n    args: {props}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
