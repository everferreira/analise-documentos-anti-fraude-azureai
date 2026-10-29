"""Modelos de dados do analisador anti-fraude."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Literal

Status = Literal["PASS", "FAIL", "WARN", "INFO"]
Severidade = Literal["info", "warn", "critical"]


@dataclass
class CampoExtraido:
    """Campo estruturado extraído do documento."""

    nome: str
    valor: str
    confianca: float = 1.0  # 0..1 (quando o provedor de OCR fornece)
    origem: str = "regex"   # regex | ocr | demo | azure


@dataclass
class Verificacao:
    """Resultado de uma regra anti-fraude."""

    regra: str                     # id estável da regra
    status: Status
    severidade: Severidade
    mensagem: str
    detalhe: str = ""


@dataclass
class Extracao:
    """Saída bruta de um provedor de extração (OCR/Azure/demo)."""

    texto: str
    confianca_media: float = 1.0
    confiancas: dict[str, float] = field(default_factory=dict)
    provedor: str = "demo"
    tempo_ms: float = 0.0


@dataclass
class RelatorioAnalise:
    """Relatório completo de uma análise anti-fraude."""

    arquivo: str
    tipo_documento: str
    provedor: str
    score_risco: int                    # 0..100 (quanto maior, maior o risco)
    classificacao: str                  # BAIXO | MEDIO | ALTO
    parecer: str                        # APROVADO | APROVADO COM RESSALVAS | REPROVADO
    campos: list[CampoExtraido] = field(default_factory=list)
    verificacoes: list[Verificacao] = field(default_factory=list)
    hash_documento: str = ""
    resumo: dict[str, Any] = field(default_factory=dict)

    @property
    def contagem(self) -> dict[str, int]:
        c = {"PASS": 0, "FAIL": 0, "WARN": 0, "INFO": 0}
        for v in self.verificacoes:
            c[v.status] = c.get(v.status, 0) + 1
        return c


def hash_arquivo(caminho: str) -> str:
    """SHA-256 do arquivo — usado para detectar duplicidade/adulteração."""
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()