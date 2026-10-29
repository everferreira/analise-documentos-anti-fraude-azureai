"""Provedor demo: extrações de referência das amostras do projeto.

Lê amostras/extracoes_demo.json (gerado por scripts/gerar_amostras.py).
Permite rodar o pipeline completo sem OCR e sem Azure.
"""

from __future__ import annotations

import json
import os

from anti_fraude.models import Extracao


def _carregar_json(amostras_dir: str) -> dict:
    caminho = os.path.join(amostras_dir, "extracoes_demo.json")
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def extrair(arquivo: str, tipo: str | None = None, amostras_dir: str | None = None) -> Extracao:
    base = os.path.basename(arquivo)
    dados = _carregar_json(amostras_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "amostras"))
    if base not in dados:
        raise FileNotFoundError(
            f"'{base}' não está no catálogo demo. Use --extractor local (OCR) ou azure, "
            f"ou rode scripts/gerar_amostras.py para regenerar o catálogo.")
    d = dados[base]
    return Extracao(
        texto=d["texto"],
        confianca_media=d.get("confianca_media", 0.99),
        confiancas=d.get("confiancas", {}),
        provedor="demo",
        tempo_ms=d.get("tempo_ms", 0.0),
    )