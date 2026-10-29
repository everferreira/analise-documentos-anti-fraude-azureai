"""Provedor Azure: Azure AI Document Intelligence (modelo prebuilt-read).

Usa apenas a biblioteca padrão (urllib) — sem SDK. Requer:
  AZURE_DOC_INTEL_ENDPOINT  (ex.: https://MEU-RECURSO.cognitiveservices.azure.com/)
  AZURE_DOC_INTEL_KEY

Documentado em README.md → seção "Ativando o modo Azure (opcional)".
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from anti_fraude.models import Extracao

API_VERSION = "2023-07-31"
MODELO = "prebuilt-read"


def _headers() -> dict:
    endpoint = os.environ.get("AZURE_DOC_INTEL_ENDPOINT", "").strip().rstrip("/")
    key = os.environ.get("AZURE_DOC_INTEL_KEY", "").strip()
    if not endpoint or not key:
        raise RuntimeError(
            "Credenciais Azure ausentes. Configure AZURE_DOC_INTEL_ENDPOINT e "
            "AZURE_DOC_INTEL_KEY (veja .env.example) ou use --extractor local/demo.")
    return {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/octet-stream",
    }


def extrair(arquivo: str, tipo: str | None = None) -> Extracao:
    heads = _headers()
    endpoint = os.environ["AZURE_DOC_INTEL_ENDPOINT"].strip().rstrip("/")
    url = (f"{endpoint}/formrecognizer/documentModels/{MODELO}"
           f":analyze?api-version={API_VERSION}")

    with open(arquivo, "rb") as f:
        corpo = f.read()

    t0 = time.monotonic()
    req = urllib.request.Request(url, data=corpo, headers=heads, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            op_location = resp.headers.get("Operation-Location")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Azure retornou HTTP {e.code}: {e.read().decode(errors='ignore')[:300]}") from e
    if not op_location:
        raise RuntimeError("Azure não devolveu Operation-Location.")

    # polling do resultado
    for _ in range(60):
        time.sleep(1.5)
        req2 = urllib.request.Request(op_location, headers={
            "Ocp-Apim-Subscription-Key": os.environ["AZURE_DOC_INTEL_KEY"].strip()})
        try:
            with urllib.request.urlopen(req2, timeout=60) as resp:
                estado = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Falha no polling Azure: HTTP {e.code}") from e
        if estado.get("status") == "succeeded":
            break
        if estado.get("status") == "failed":
            raise RuntimeError(f"Azure falhou a análise: {estado.get('error')}")
    else:
        raise RuntimeError("Timeout esperando a análise do Azure.")

    # extrai linhas de texto + confiança média por página
    linhas: list[str] = []
    scores: list[float] = []
    for pagina in estado.get("analyzeResult", {}).get("readResults", []):
        for linha in pagina.get("lines", []):
            texto = linha.get("text", "").strip()
            if texto:
                linhas.append(texto)
    for item in estado.get("analyzeResult", {}).get("readResults", []):
        for linha in item.get("lines", []):
            for palavra in linha.get("words", []):
                scores.append(float(palavra.get("confidence", 0)))

    conf_media = round(sum(scores) / len(scores), 3) if scores else 0.0
    return Extracao(
        texto="\n".join(linhas),
        confianca_media=conf_media,
        confiancas={},
        provedor="azure-docintelligence",
        tempo_ms=round((time.monotonic() - t0) * 1000, 1),
    )