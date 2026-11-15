"""Gera as capturas de tela usadas no README (docs/img).

uvicorn painel.app:app --port 8000   # em outro terminal
python scripts/capturar_telas.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
DESTINO = Path(__file__).resolve().parent.parent / "docs" / "img"

PAGINAS = {
    "panorama": "/",
    "territorio": "/territorio",
    "gestao": "/gestao",
    "acessibilidade": "/acessibilidade",
    "qualidade": "/qualidade",
    "panorama-nordeste": "/?regiao=NE",
}


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        erros: list[str] = []
        pagina.on("console", lambda m: erros.append(f"{m.type}: {m.text}") if m.type == "error" else None)
        for nome, caminho in PAGINAS.items():
            pagina.goto(BASE + caminho, wait_until="networkidle")
            pagina.wait_for_selector(".plot .main-svg", timeout=30_000)
            pagina.wait_for_timeout(800)
            pagina.screenshot(path=DESTINO / f"{nome}.png", full_page=nome != "panorama")
            print("ok", nome)

        if "--agente" in sys.argv:
            # Pergunta real ao agente (gasta chamadas da API Gemini).
            pagina.goto(BASE + "/agente", wait_until="networkidle")
            pagina.click("text=Qual a maior cidade do Nordeste sem nenhum museu ativo?")
            pagina.wait_for_selector(".msg-agente:not(.msg-carregando)", timeout=180_000)
            pagina.click(".rastro summary")
            pagina.wait_for_timeout(500)
            pagina.screenshot(path=DESTINO / "agente.png", full_page=True)
            print("ok agente")
        navegador.close()
    if erros:
        print("\n".join(erros))


def interacoes(base: str = BASE) -> None:
    """Paleta de comandos, clique no mapa e gaveta do agente aberta a partir de um gráfico."""
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page(viewport={"width": 1440, "height": 900})
        erros: list[str] = []
        pagina.on("pageerror", lambda e: erros.append(str(e)))
        pagina.goto(base + "/", wait_until="networkidle")
        pagina.wait_for_selector("#g-mapa .main-svg")

        pagina.keyboard.press("Control+k")
        pagina.fill("#paleta-busca", "nordeste")
        pagina.wait_for_timeout(300)
        pagina.screenshot(path=DESTINO / "paleta.png")
        pagina.keyboard.press("Escape")

        pagina.mouse.click(5, 5)
        pagina.keyboard.press("ArrowRight")  # próximo recorte
        pagina.wait_for_url("**regiao=**")
        print("seta direita ->", pagina.url)

        pagina.goto(base + "/", wait_until="networkidle")
        pagina.wait_for_selector("#g-mapa .main-svg")
        # O Plotly põe uma camada de eventos por cima dos polígonos: clica nas coordenadas, como o mouse faria.
        pagina.locator("#g-mapa").scroll_into_view_if_needed()
        caixa = pagina.locator("#g-mapa .choroplethlocation").nth(5).bounding_box()
        pagina.mouse.move(caixa["x"] + caixa["width"] / 2, caixa["y"] + caixa["height"] / 2, steps=5)
        pagina.mouse.click(caixa["x"] + caixa["width"] / 2, caixa["y"] + caixa["height"] / 2)
        pagina.wait_for_url("**uf=**")
        print("clique no mapa ->", pagina.url)

        if "--agente" in sys.argv:
            pagina.goto(base + "/", wait_until="networkidle")
            pagina.wait_for_selector(".perguntar-sobre")
            pagina.click("#g-regioes")  # garante foco fora de inputs
            pagina.click(".cartao-mapa .perguntar-sobre")
            pagina.wait_for_selector("#gaveta .msg-agente:not(.msg-carregando)", timeout=180_000)
            pagina.wait_for_timeout(400)
            pagina.screenshot(path=DESTINO / "gaveta-agente.png")
            print("ok gaveta")
        navegador.close()
        if erros:
            print("ERROS JS:", erros)


if __name__ == "__main__":
    main()
    interacoes()
