"""Provedor local: OCR com RapidOCR (ONNX Runtime) — sem instalação de
sistema, sem chave, sem internet. Tudo roda em userspace via pip."""

from __future__ import annotations

import time

from anti_fraude.models import Extracao


def extrair(arquivo: str, tipo: str | None = None) -> Extracao:
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as e:
        raise RuntimeError(
            "RapidOCR não instalado. Rode: uv pip install --python <venv> rapidocr-onnxruntime"
        ) from e

    t0 = time.monotonic()
    engine = RapidOCR()
    resultado, _ = engine(arquivo)

    linhas: list[str] = []
    confiancas: dict[str, float] = {}
    scores: list[float] = []
    for item in resultado or []:
        # item: [box, texto, score]
        texto = str(item[1]).strip()
        score = float(item[2])
        if texto:
            linhas.append(texto)
            confiancas[texto] = round(score, 3)
            scores.append(score)

    texto = "\n".join(linhas)
    conf_media = round(sum(scores) / len(scores), 3) if scores else 0.0
    return Extracao(
        texto=texto,
        confianca_media=conf_media,
        confiancas=confiancas,
        provedor="local-rapidocr",
        tempo_ms=round((time.monotonic() - t0) * 1000, 1),
    )