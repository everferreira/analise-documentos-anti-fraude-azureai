"""Cálculo do score de risco e classificação do parecer."""

from __future__ import annotations

from .models import RelatorioAnalise, Verificacao

# Peso de cada severidade de falha (quanto maior, mais grave)
PESO = {"info": 0, "warn": 12, "critical": 30}


def calcular_score(verificacoes: list[Verificacao]) -> int:
    """Score 0-100: acumula peso das falhas, teto de 100."""
    score = min(100, sum(PESO[v.severidade] for v in verificacoes if v.status in ("FAIL", "WARN")))
    return score


def classificar(score: int) -> str:
    if score < 25:
        return "BAIXO"
    if score < 55:
        return "MEDIO"
    return "ALTO"


def parecer(verificacoes: list[Verificacao]) -> str:
    criticos = [v for v in verificacoes if v.status == "FAIL" and v.severidade == "critical"]
    if criticos:
        return "REPROVADO"
    if any(v.status == "WARN" for v in verificacoes):
        return "APROVADO COM RESSALVAS"
    return "APROVADO"


def gerar_relatorio(**kw) -> RelatorioAnalise:
    """Monta o RelatorioAnalise a partir das verificações."""
    verificacoes = kw.pop("verificacoes")
    score = calcular_score(verificacoes)
    rel = RelatorioAnalise(
        score_risco=score,
        classificacao=classificar(score),
        parecer=parecer(verificacoes),
        verificacoes=verificacoes,
        **kw,
    )
    rel.resumo = {
        "score": score,
        "classificacao": rel.classificacao,
        "parecer": rel.parecer,
        "contagem": rel.contagem,
        "n_campos": len(rel.campos),
    }
    return rel