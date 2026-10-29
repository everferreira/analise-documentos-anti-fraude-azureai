#!/usr/bin/env python3
"""CLI de análise anti-fraude de documentos.

Uso:
    python3 src/cli.py --todos [--extractor auto|demo|local|azure] [--cadastro cadastro.json]
    python3 src/cli.py amostras/rg_adulterado.png --tipo rg --extractor local
    python3 src/cli.py arquivo.pdf --extractor azure --json

Exemplos:
    # analisa todas as amostras com OCR local real
    python3 src/cli.py --todos --extractor local --cadastro scripts/cadastro.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from anti_fraude import aplicar_regras, gerar_relatorio, parse_campos, TIPOS_VALIDOS  # noqa: E402
from extractors import PROVEDORES, obter_extrator  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AMOSTRAS = os.path.join(RAIZ, "amostras")


def detectar_tipo(arquivo: str) -> str | None:
    nome = os.path.basename(arquivo).lower()
    for t in ("rg", "cnh", "nf", "boleto", "comprovante"):
        if t in nome:
            return t
    return None


def carregar_cadastro(caminho: str | None) -> dict | None:
    if not caminho:
        return None
    if not os.path.exists(caminho):
        print(f"⚠️  Cadastro '{caminho}' não encontrado — seguindo sem cruzamento.", file=sys.stderr)
        return None
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def analisar(arquivo: str, tipo: str | None, extrator, cadastro: dict | None,
             armadilha: set) -> dict:
    if tipo == "auto" or not tipo:
        tipo = detectar_tipo(arquivo)
    extracao = extrator(arquivo, tipo)
    campos = parse_campos(extracao.texto, tipo, extracao.confiancas)
    verificacoes = aplicar_regras(campos, tipo, arquivo, cadastro, extracao, armadilha)
    from anti_fraude import hash_arquivo
    rel = gerar_relatorio(
        arquivo=os.path.basename(arquivo), tipo_documento=tipo or "auto",
        provedor=extracao.provedor, campos=campos,
        verificacoes=verificacoes, hash_documento=hash_arquivo(arquivo),
    )
    # monta dict serializável
    return {
        "arquivo": rel.arquivo,
        "tipo": rel.tipo_documento,
        "provedor": rel.provedor,
        "score": rel.score_risco,
        "classificacao": rel.classificacao,
        "parecer": rel.parecer,
        "tempo_ms": extracao.tempo_ms,
        "confianca_ocr": extracao.confianca_media,
        "hash": rel.hash_documento,
        "campos": [{"nome": c.nome, "valor": c.valor, "confianca": c.confianca} for c in rel.campos],
        "verificacoes": [{"regra": v.regra, "status": v.status, "severidade": v.severidade,
                          "mensagem": v.mensagem, "detalhe": v.detalhe} for v in rel.verificacoes],
        "resumo": rel.resumo,
    }


def imprimir_relatorio(r: dict, verbozo: bool = True) -> None:
    cor = {"BAIXO": "\033[92m", "MEDIO": "\033[93m", "ALTO": "\033[91m"}.get(r["classificacao"], "")
    reset = "\033[0m"
    negrito = "\033[1m"
    linha = "─" * 74
    print(f"\n{linha}")
    print(f" {negrito}{r['arquivo']}{reset}  [{r['tipo'] or 'auto'}]  via {r['provedor']}")
    print(linha)
    print(f"  Score de risco : {cor}{r['score']:3d}/100{reset}  →  {cor}{negrito}{r['classificacao']}{reset}")
    print(f"  Parecer        : {r['parecer']}")
    print(f"  Confiança OCR  : {r['confianca_ocr']:.0%}   (tempo: {r['tempo_ms']:.0f} ms)")
    print(f"  SHA-256        : {r['hash'][:24]}…")
    if not verbozo:
        return
    if r["campos"]:
        print(f"\n  Campos extraídos:")
        for c in r["campos"]:
            conf = f" ({c['confianca']:.0%})" if c["confianca"] < 1 else ""
            print(f"    • {c['nome']:<12}: {c['valor']}{conf}")
    print(f"\n  Verificações:")
    simbolo = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️ ", "INFO": "ℹ️ "}
    for v in r["verificacoes"]:
        print(f"    {simbolo.get(v['status'], '?')} [{v['regra']}] {v['mensagem']}")
        if v["detalhe"]:
            print(f"        ↳ {v['detalhe']}")
    print(linha)


def main() -> int:
    ap = argparse.ArgumentParser(description="Análise anti-fraude de documentos (Azure AI / OCR local / demo)")
    ap.add_argument("arquivos", nargs="*", help="documento(s) a analisar")
    ap.add_argument("--todos", action="store_true", help="analisa todas as amostras em amostras/")
    ap.add_argument("--extractor", choices=PROVEDORES, default="auto", help="provedor de extração")
    ap.add_argument("--tipo", choices=["auto"] + TIPOS_VALIDOS, default="auto", help="tipo do documento")
    ap.add_argument("--cadastro", default=None, help="JSON da base de cadastro (scripts/cadastro.json)")
    ap.add_argument("--json", action="store_true", help="saída em JSON")
    ap.add_argument("--amostras-dir", default=AMOSTRAS, help="diretório das amostras")
    args = ap.parse_args()

    if not args.arquivos and not args.todos:
        ap.print_help()
        return 2

    extrator = obter_extrator(args.extractor, args.amostras_dir)
    cadastro = carregar_cadastro(args.cadastro)
    armadilha: set = set()

    if args.todos:
        imgs = sorted(f for f in os.listdir(args.amostras_dir)
                      if f.lower().endswith((".png", ".jpg", ".jpeg", ".pdf")) and f != "extracoes_demo.json")
        arquivos = [os.path.join(args.amostras_dir, f) for f in imgs]
    else:
        arquivos = args.arquivos

    resultados = []
    for arq in arquivos:
        if not os.path.exists(arq):
            print(f"❌ Arquivo não encontrado: {arq}", file=sys.stderr)
            continue
        try:
            r = analisar(arq, args.tipo, extrator, cadastro, armadilha)
            resultados.append(r)
            if args.json:
                print(json.dumps(r, ensure_ascii=False, indent=2))
            else:
                imprimir_relatorio(r)
        except Exception as e:
            print(f"❌ Erro ao analisar {arq}: {e}", file=sys.stderr)

    if args.json and resultados:
        print(json.dumps(resultados, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())