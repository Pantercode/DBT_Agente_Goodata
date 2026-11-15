"""Entrada da Vercel (runtime Python). Toda rota cai aqui via rewrite no vercel.json."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from painel.app import app

__all__ = ["app"]
