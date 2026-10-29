"""Parser de campos estruturados a partir do texto bruto (OCR/Azure/demo).

A ideia: o provedor de extração devolve texto + confianças; este módulo
transforma o texto em campos estruturados (nome, CPF, CNPJ, datas, valores...)
usando padrões brasileiros. O motor de regras só enxerga os campos.
"""

from __future__ import annotations

import re

from .models import CampoExtraido

# Padrões otimizados para o texto normalizado (espaços colapsados, maiúsculas)
RE_CPF = re.compile(r"\b(\d{3}\.\d{3}\.\d{3}-\d{2})\b")
RE_CNPJ = re.compile(r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b")
RE_RG = re.compile(r"\b(\d{1,2}\.?\d{3}\.?\d{3}-?\d{1,2})\b")
RE_DATA = re.compile(r"\b(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})\b")
RE_VALOR = re.compile(r"(?:R\$\s?)?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})")
RE_CEP = re.compile(r"\b(\d{5}-?\d{3})\b")
RE_PLACA = re.compile(r"\b([A-Z]{3}\d[A-Z0-9]\d{2}|[A-Z]{3}-?\d{4})\b")
RE_CNH = re.compile(r"\b(\d{11})\b")

ROTULO_DATA = {
    "nascimento": r"(?:NASCIMENTO|NASC|DATA\s+DE\s+NASCIMENTO|DN\b)",
    "emissao": r"(?:EMISS[AÃ]O|DATA\s+(?:DE\s+)?EMISS[AÃ]O|EXPEDI[CÇ][AÃ]O|EMITIDO\s+EM)",
    "validade": r"(?:VALIDADE|VALIDO\s+ATE|EXPIRA)",
    "vencimento": r"(?:VENCIMENTO|VENCE|PAGAVEL\s+ATE)",
}

ROTULO_NOME = r"(?:NOME|CLIENTE|FAVORECIDO|BENEFICI[AÁ]RIO|TITULAR|SACADO)"
ROTULO_ENDERECO = r"(?:ENDERE[ÇC]O|RUA|AVENIDA|LOGRADOURO|AV\b)"


def _texto_normalizado(texto: str) -> str:
    return re.sub(r"\s+", " ", texto.upper())


def _pega_grupo(texto: str, regex: re.Pattern, rotulo: str,
                confianca: float = 1.0) -> CampoExtraido | None:
    """Procura 'ROTULO: <valor>' ou valor próximo ao rótulo no texto."""
    m = re.search(rf"{rotulo}\s*[:;.\-]?\s*([A-Z0-9À-Ú.,/\- ]{{3,60}}?)(?:\s{2,}|\|)", texto)
    if m:
        valor = m.group(1).strip().strip(".;:")
        if valor:
            return CampoExtraido("nome" if "nome" in rotulo else "rotulo", valor, confianca)
    return None


def parse_campos(texto: str, tipo: str | None = None, confiancas: dict | None = None) -> list[CampoExtraido]:
    """Extrai campos estruturados do texto. `tipo` restringe o que procurar."""
    t = _texto_normalizado(texto)
    confiancas = confiancas or {}
    campos: list[CampoExtraido] = []

    def add(nome: str, valor: str, conf: float = 1.0, origem: str = "regex"):
        if valor and not any(c.nome == nome and c.valor == valor for c in campos):
            campos.append(CampoExtraido(nome, valor, conf, origem))

    tipo = (tipo or "").lower()

    # ------------------------- campos de identidade -------------------------
    if tipo in ("", "rg", "cnh", "comprovante"):
        if m := RE_CPF.search(t):
            add("cpf", m.group(1))
        if m := RE_CNH.search(t):
            add("cnh", m.group(1))
        if tipo in ("rg", "cnh") or "REGISTRO GERAL" in t or re.search(r"\bRG\b", t):
            # prefere o número que segue "REGISTRO GERAL"; evita capturar CPF
            m = re.search(r"REGISTRO\s+GERAL\s*[:.\-]?\s*(\d{1,2}\.?\d{3}\.?\d{3}-?\d{1,2})", t)
            if not m:
                m = RE_RG.search(t)
            if m:
                add("rg", m.group(1))
        if m := RE_PLACA.search(t):
            if tipo in ("", "comprovante"):
                add("placa", m.group(1))

    # ------------------------------ CNPJ / NF -------------------------------
    if tipo in ("", "nf", "boleto"):
        if m := RE_CNPJ.search(t):
            add("cnpj", m.group(1))

    # -------------------------------- nomes ---------------------------------
    if tipo in ("", "rg", "cnh", "boleto", "comprovante"):
        m = re.search(rf"{ROTULO_NOME}\s*[:;.\-]?\s*([A-ZÀ-Ú][A-ZÀ-Ú\s.'\-]{{4,60}})", t)
        if m:
            nome = m.group(1).strip()
            # aparar rótulos que vêm na sequência do nome (OCR/demo unem linhas)
            nome = re.split(r"\s+(?:CPF|FILIACAO|RG\b|NASCIMENTO|EMISSAO|VALIDADE|ENDERECO|CEP|ITENS)\b", nome)[0]
            add("nome", nome.strip())

    # -------------------------------- datas ---------------------------------
    for rotulo, padrao in ROTULO_DATA.items():
        m = re.search(rf"{padrao}\s*[:;.\-]?\s*(\d{{1,2}}[/\-.]\d{{1,2}}[/\-.]\d{{2,4}})", t)
        if m:
            add(rotulo, m.group(1))

    # datas avulsas ordenadas (para docs sem rótulo)
    if tipo in ("rg", "cnh"):
        datas = RE_DATA.findall(t)
        if datas and not campo_nome(campos, "nascimento"):
            add("nascimento", datas[0])
        if len(datas) > 1 and not campo_nome(campos, "emissao"):
            add("emissao", datas[1])

    # ------------------------------ endereço --------------------------------
    if tipo in ("", "comprovante"):
        m = re.search(rf"{ROTULO_ENDERECO}\s*[:;.\-]?\s*([A-Z0-9À-Ú.,\s/\-]{{5,60}})", t)
        if m:
            add("endereco", m.group(1).strip())
        if m := RE_CEP.search(t):
            add("cep", m.group(1))

    # ------------------------------- valores --------------------------------
    if tipo in ("", "nf", "boleto"):
        # distingue TOTAL (nota fiscal) de VALOR (boleto)
        m = re.search(r"(?P<rot>TOTAL|VALOR)\s*[:;.\-]?\s*R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})", t)
        if m:
            if m.group("rot") == "TOTAL":
                add("total", m.group(2))
            else:
                add("valor", m.group(2))
        elif tipo != "boleto":
            valores = RE_VALOR.findall(t)
            if valores:
                add("total", valores[-1])
        # itens da NF: todos os valores monetários, exceto o total.
        # (robusto ao OCR que quebra linhas — o nome do item não é usado nas regras)
        if tipo == "nf":
            total_itens = {c.valor for c in campos if c.nome == "total"}
            for v in RE_VALOR.findall(t):
                if v in total_itens:
                    continue
                n = f"item{len([c for c in campos if c.nome.startswith('item')]) + 1}"
                if not any(c.nome.startswith("item") and c.valor == v for c in campos):
                    add(n, v)
        if tipo == "boleto" and "total" not in {c.nome for c in campos}:
            # compatibilidade: regras tratam "total" e "valor" como sinônimos
            for c in campos:
                if c.nome == "valor":
                    add("total", c.valor)

    # confianças por campo
    for c in campos:
        if c.valor in confiancas:
            c.confianca = confiancas[c.valor]
    return campos


def campo_nome(campos: list[CampoExtraido], nome: str) -> CampoExtraido | None:
    for c in campos:
        if c.nome == nome:
            return c
    return None