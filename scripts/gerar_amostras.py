#!/usr/bin/env python3
"""Gera documentos de exemplo SINTÉTICOS (100% fictícios) para o projeto.

- Cria PNGs em amostras/ (RG ok/adulterado, NF ok/suspeita, boleto, comprovante)
- Escreve amostras/extracoes_demo.json (catálogo para o provedor demo)
- Escreve scripts/cadastro.json (base de cadastro para cruzamento)
- Copia as imagens para web/samples/ (produto online)

CPFs e CNPJs são gerados com dígitos verificadores reais (algoritmo oficial)
— os documentos "adulterados" recebem versões com dígito corrompido.

Uso:
    /home/conta/dio-venv/bin/python scripts/gerar_amostras.py
"""

from __future__ import annotations

import json
import os
import random

from PIL import Image, ImageDraw, ImageFont

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AMOSTRAS = os.path.join(RAIZ, "amostras")
WEB_SAMPLES = os.path.join(RAIZ, "web", "samples")
SCRIPTS = os.path.join(RAIZ, "scripts")

FONTE_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONTE_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# ─────────────────────────────────────────────────────────────────────────────
# Validador/gerador de CPF e CNPJ (dígitos verificadores oficiais)
# ─────────────────────────────────────────────────────────────────────────────

def dv_cpf(d: str) -> str:
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        resto = soma % 11
        d += "0" if resto < 2 else str(11 - resto)
    return d[-2:]


def cpf_valido() -> str:
    while True:
        base = "".join(str(random.randint(0, 9)) for _ in range(9))
        if len(set(base)) > 1:
            return base + dv_cpf(base)


def dv_cnpj(d: str) -> str:
    for pesos in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
                  [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        soma = sum(int(d[i]) * pesos[i] for i in range(len(pesos)))
        resto = soma % 11
        d += "0" if resto < 2 else str(11 - resto)
    return d[-2:]


def cnpj_valido() -> str:
    while True:
        base = "".join(str(random.randint(0, 9)) for _ in range(8)) + "0001"
        if len(set(base)) > 1:
            return base + dv_cnpj(base)


def corromper(v: str) -> str:
    """Troca o último dígito por outro (deixa o documento 'adulterado')."""
    ultimo = int(v[-1])
    return v[:-1] + str((ultimo + 1) % 10)


def fmt_cpf(v: str) -> str:
    return f"{v[:3]}.{v[3:6]}.{v[6:9]}-{v[9:]}"


def fmt_cnpj(v: str) -> str:
    return f"{v[:2]}.{v[2:5]}.{v[5:8]}/{v[8:12]}-{v[12:]}"


# ─────────────────────────────────────────────────────────────────────────────
# Desenho dos documentos (PIL)
# ─────────────────────────────────────────────────────────────────────────────

def _fonte(tamanho: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONTE_BOLD if bold else FONTE_REG, tamanho)


def desenhar_documento(linhas: list[tuple[str, str]], titulo: str,
                       largura: int = 1100, foto: bool = False) -> Image.Image:
    """linhas: [(rotulo, valor)]. Desenha um documento limpo estilo formulário."""
    alto = 120 + len(linhas) * 74 + (260 if foto else 80)
    img = Image.new("RGB", (largura, alto), "#ffffff")
    d = ImageDraw.Draw(img)
    d.rectangle([12, 12, largura - 12, alto - 12], outline="#2b3a67", width=3)

    # título
    ft = _fonte(40, bold=True)
    tw = d.textlength(titulo, font=ft)
    d.text(((largura - tw) / 2, 40), titulo, font=ft, fill="#1f2a44")

    # moldura de foto (RG/CNH)
    y = 130
    if foto:
        d.rectangle([largura - 320, y, largura - 90, y + 240], outline="#8a93a8",
                    width=2, fill="#f2f4f8")
        d.text((largura - 290, y + 100), "FOTO", font=_fonte(22), fill="#8a93a8")

    y += 20
    for rotulo, valor in linhas:
        d.text((70, y), rotulo.upper() + ":", font=_fonte(24, bold=True), fill="#3a4a6b")
        d.text((360, y), valor, font=_fonte(26), fill="#0d1424")
        y += 74

    d.text((70, y + 10), "Documento sintético para fins de demonstração — todos os dados são fictícios.",
           font=_fonte(18), fill="#9aa3b5")
    return img


# ─────────────────────────────────────────────────────────────────────────────
# Conteúdo das amostras
# ─────────────────────────────────────────────────────────────────────────────

def montar_amostras() -> dict:
    """Gera todas as imagens e devolve {arquivo: {texto, tipo, confianca_media}}."""
    random.seed(42)
    os.makedirs(AMOSTRAS, exist_ok=True)
    os.makedirs(WEB_SAMPLES, exist_ok=True)

    cpf_joao = cpf_valido()
    cnpj_xyz = cnpj_valido()

    catalogo: dict[str, dict] = {}

    def registrar(nome: str, tipo: str, texto: str):
        catalogo[nome] = {"tipo": tipo, "texto": texto, "confianca_media": 0.98}

    # ── RG OK ────────────────────────────────────────────────────────────────
    nome = "rg_ok.png"
    texto = (
        "REGISTRO GERAL (RG)\n"
        "NOME: JOAO PEREIRA DA SILVA\n"
        "FILIACAO: CARLOS PEREIRA DA SILVA / MARIA HELENA SOUZA\n"
        "REGISTRO GERAL: 12.345.678-9\n"
        "ORGAO EMISSOR: SSP/SP\n"
        f"CPF: {fmt_cpf(cpf_joao)}\n"
        "NASCIMENTO: 15/03/1990\n"
        "EMISSAO: 10/01/2024\n"
        "VALIDADE: 10/01/2034"
    )
    img = desenhar_documento(
        [("Nome", "JOAO PEREIRA DA SILVA"),
         ("Filiação", "CARLOS PEREIRA DA SILVA / MARIA HELENA SOUZA"),
         ("Registro Geral", "12.345.678-9"),
         ("Órgão Emissor", "SSP/SP"),
         ("CPF", fmt_cpf(cpf_joao)),
         ("Nascimento", "15/03/1990"),
         ("Emissão", "10/01/2024"),
         ("Validade", "10/01/2034")],
        "REGISTRO GERAL (RG)", foto=True)
    img.save(os.path.join(AMOSTRAS, nome))
    registrar(nome, "rg", texto)

    # ── RG ADULTERADO (CPF inválido + validade expirada) ─────────────────────
    nome = "rg_adulterado.png"
    cpf_fake = corromper(cpf_joao)
    texto = (
        "REGISTRO GERAL (RG)\n"
        "NOME: JOAO PEREIRA DA SILVA\n"
        "FILIACAO: CARLOS PEREIRA DA SILVA / MARIA HELENA SOUZA\n"
        "REGISTRO GERAL: 12.345.678-9\n"
        "ORGAO EMISSOR: SSP/SP\n"
        f"CPF: {fmt_cpf(cpf_fake)}\n"
        "NASCIMENTO: 15/03/1990\n"
        "EMISSAO: 10/01/2024\n"
        "VALIDADE: 10/01/2025"
    )
    img = desenhar_documento(
        [("Nome", "JOAO PEREIRA DA SILVA"),
         ("Filiação", "CARLOS PEREIRA DA SILVA / MARIA HELENA SOUZA"),
         ("Registro Geral", "12.345.678-9"),
         ("Órgão Emissor", "SSP/SP"),
         ("CPF", fmt_cpf(cpf_fake)),
         ("Nascimento", "15/03/1990"),
         ("Emissão", "10/01/2024"),
         ("Validade", "10/01/2025")],
        "REGISTRO GERAL (RG)", foto=True)
    img.save(os.path.join(AMOSTRAS, nome))
    registrar(nome, "rg", texto)

    # ── NOTA FISCAL OK ───────────────────────────────────────────────────────
    nome = "nf_ok.png"
    texto = (
        "NOTA FISCAL DE VENDA Nº 000123\n"
        "EMITENTE: COMERCIO DE MATERIAIS XYZ LTDA\n"
        f"CNPJ: {fmt_cnpj(cnpj_xyz)}\n"
        "DATA EMISSAO: 05/05/2026\n"
        "ITENS:\n"
        "CANETA ESFEROGRÁFICA .......... R$ 10,00\n"
        "CADERNO 96 FOLHAS ............... R$ 25,50\n"
        "MOCHILA ESCOLAR ................. R$ 89,90\n"
        "TOTAL: R$ 125,40"
    )
    img = desenhar_documento(
        [("Emitente", "COMERCIO DE MATERIAIS XYZ LTDA"),
         ("CNPJ", fmt_cnpj(cnpj_xyz)),
         ("Data Emissão", "05/05/2026"),
         ("Item 1", "CANETA ESFEROGRÁFICA .......... R$ 10,00"),
         ("Item 2", "CADERNO 96 FOLHAS ............... R$ 25,50"),
         ("Item 3", "MOCHILA ESCOLAR ................. R$ 89,90"),
         ("Total", "R$ 125,40")],
        "NOTA FISCAL DE VENDA Nº 000123")
    img.save(os.path.join(AMOSTRAS, nome))
    registrar(nome, "nf", texto)

    # ── NOTA FISCAL SUSPEITA (CNPJ inválido + total ≠ soma) ──────────────────
    nome = "nf_suspeita.png"
    cnpj_fake = corromper(cnpj_xyz)
    texto = (
        "NOTA FISCAL DE VENDA Nº 000124\n"
        "EMITENTE: COMERCIO DE MATERIAIS XYZ LTDA\n"
        f"CNPJ: {fmt_cnpj(cnpj_fake)}\n"
        "DATA EMISSAO: 05/05/2026\n"
        "ITENS:\n"
        "CANETA ESFEROGRÁFICA .......... R$ 10,00\n"
        "CADERNO 96 FOLHAS ............... R$ 25,50\n"
        "MOCHILA ESCOLAR ................. R$ 89,90\n"
        "TOTAL: R$ 155,40"
    )
    img = desenhar_documento(
        [("Emitente", "COMERCIO DE MATERIAIS XYZ LTDA"),
         ("CNPJ", fmt_cnpj(cnpj_fake)),
         ("Data Emissão", "05/05/2026"),
         ("Item 1", "CANETA ESFEROGRÁFICA .......... R$ 10,00"),
         ("Item 2", "CADERNO 96 FOLHAS ............... R$ 25,50"),
         ("Item 3", "MOCHILA ESCOLAR ................. R$ 89,90"),
         ("Total", "R$ 155,40")],
        "NOTA FISCAL DE VENDA Nº 000124")
    img.save(os.path.join(AMOSTRAS, nome))
    registrar(nome, "nf", texto)

    # ── BOLETO OK ────────────────────────────────────────────────────────────
    nome = "boleto_ok.png"
    texto = (
        "BOLETO DE COBRANCA\n"
        "FAVORECIDO: EMPRESA DE ENERGIA SA\n"
        "SACADO: JOAO PEREIRA DA SILVA\n"
        "VALOR: R$ 187,42\n"
        "VENCIMENTO: 20/11/2026\n"
        "LINHA DIGITAVEL: 23793.38128 60007.827113 95000.063305 7 83690000018742"
    )
    img = desenhar_documento(
        [("Favorecido", "EMPRESA DE ENERGIA SA"),
         ("Sacado", "JOAO PEREIRA DA SILVA"),
         ("Valor", "R$ 187,42"),
         ("Vencimento", "20/11/2026"),
         ("Linha Digitável", "23793.38128 60007.827113 95000.063305 7 83690000018742")],
        "BOLETO DE COBRANCA")
    img.save(os.path.join(AMOSTRAS, nome))
    registrar(nome, "boleto", texto)

    # ── COMPROVANTE INCONSISTENTE (nome ≠ cadastro) ──────────────────────────
    nome = "comprovante_inconsistente.png"
    texto = (
        "COMPROVANTE DE RESIDENCIA\n"
        "NOME: CARLOS ALBERTO DE SOUZA\n"
        f"CPF: {fmt_cpf(cpf_joao)}\n"
        "ENDERECO: RUA DAS FLORES, 123 - SAO PAULO/SP\n"
        "CEP: 01234-567\n"
        "DATA EMISSAO: 01/08/2026"
    )
    img = desenhar_documento(
        [("Nome", "CARLOS ALBERTO DE SOUZA"),
         ("CPF", fmt_cpf(cpf_joao)),
         ("Endereço", "RUA DAS FLORES, 123 - SAO PAULO/SP"),
         ("CEP", "01234-567"),
         ("Data Emissão", "01/08/2026")],
        "COMPROVANTE DE RESIDENCIA")
    img.save(os.path.join(AMOSTRAS, nome))
    registrar(nome, "comprovante", texto)

    # ── Catálogo demo + cadastro + cópia web ─────────────────────────────────
    with open(os.path.join(AMOSTRAS, "extracoes_demo.json"), "w", encoding="utf-8") as f:
        json.dump(catalogo, f, ensure_ascii=False, indent=2)

    cadastro = {
        cpf_joao: {"nome": "JOAO PEREIRA DA SILVA", "cidade": "SAO PAULO",
                   "score_base": 0.2, "observacao": "cliente desde 2019"},
    }
    with open(os.path.join(SCRIPTS, "cadastro.json"), "w", encoding="utf-8") as f:
        json.dump(cadastro, f, ensure_ascii=False, indent=2)

    for arq in os.listdir(AMOSTRAS):
        if arq.lower().endswith((".png", ".jpg", ".jpeg")):
            import shutil
            shutil.copy(os.path.join(AMOSTRAS, arq), os.path.join(WEB_SAMPLES, arq))

    return catalogo


if __name__ == "__main__":
    catalogo = montar_amostras()
    print(f"Amostras geradas: {len(catalogo)}")
    for nome in catalogo:
        print(f"  - {nome}  [{catalogo[nome]['tipo']}]")
    print("Cadastro e catálogo demo atualizados.")