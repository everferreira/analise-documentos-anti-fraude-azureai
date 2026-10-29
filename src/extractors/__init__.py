"""Provedores de extração de texto de documentos.

Arquitetura plugável: o mesmo pipeline (parser + regras) funciona com
qualquer provedor. Os disponíveis:

- demo:   extrações de referência embutidas (amostras/extracoes_demo.json)
          — funciona sem nenhuma dependência, usado para testes/demo.
- local:  OCR real em máquina local via RapidOCR (ONNX, sem instalação de
          sistema, sem internet).
- azure:  Azure AI Document Intelligence (modelo prebuilt-read) via REST —
          requer AZURE_DOC_INTEL_ENDPOINT + AZURE_DOC_INTEL_KEY no .env.
"""

from __future__ import annotations

import os
from typing import Callable

from anti_fraude.models import Extracao

RAIZ_PROJETO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AMOSTRAS_DIR = os.path.join(RAIZ_PROJETO, "amostras")


def obter_extrator(nome: str, amostras_dir: str | None = None):
    """Factory dos provedores."""
    nome = (nome or "auto").lower()
    if nome == "demo":
        from . import demo
        return lambda p, t: demo.extrair(p, t, amostras_dir or AMOSTRAS_DIR)
    if nome == "local":
        from . import local
        return local.extrair
    if nome == "azure":
        from . import azure
        return azure.extrair
    if nome == "auto":
        try:
            from . import local  # noqa: F401
            if _rapidocr_disponivel():
                return local.extrair
        except Exception:
            pass
        from . import demo
        return lambda p, t: demo.extrair(p, t, amostras_dir or AMOSTRAS_DIR)
    raise ValueError(f"Extrator desconhecido: {nome} (use auto|demo|local|azure)")


def _rapidocr_disponivel() -> bool:
    try:
        import rapidocr_onnxruntime  # noqa: F401
        return True
    except Exception:
        return False


PROVEDORES = ["auto", "demo", "local", "azure"]