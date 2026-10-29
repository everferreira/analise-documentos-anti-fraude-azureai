"""Motor de regras anti-fraude.

Cada função recebe os campos extraídos + cadastro de referência e devolve
uma lista de Verificacao. Nenhuma regra depende de provedor de OCR — todas
operam sobre os campos já estruturados, o que garante o mesmo comportamento
com Azure, OCR local ou modo demo.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from .models import CampoExtraido, Verificacao

# ─────────────────────────────────────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────────────────────────────────────

def so_digitos(v: str) -> str:
    return re.sub(r"\D", "", v or "")


def normalizar_nome(v: str) -> str:
    """Maiúsculas, sem acentos, espaços colapsados."""
    v = unicodedata.normalize("NFD", v or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", v.upper()).strip()


def parse_data(v: str):
    """dd/mm/aaaa (ou dd-mm-aaaa) -> date | None. Aceita 2 ou 4 dígitos no ano."""
    m = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", v or "")
    if not m:
        return None
    d, mes, ano = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if ano < 100:
        ano += 2000 if ano <= 40 else 1900
    try:
        from datetime import date
        return date(ano, mes, d)
    except ValueError:
        return None


def campo(campos: list[CampoExtraido], nome: str) -> CampoExtraido | None:
    for c in campos:
        if c.nome.lower() == nome.lower():
            return c
    return None


def P(regra: str, msg: str, detalhe: str = "") -> Verificacao:
    return Verificacao(regra, "PASS", "info", msg, detalhe)


def F(regra: str, msg: str, detalhe: str = "", sev: str = "critical") -> Verificacao:
    return Verificacao(regra, "FAIL", sev, msg, detalhe)


def W(regra: str, msg: str, detalhe: str = "") -> Verificacao:
    return Verificacao(regra, "WARN", "warn", msg, detalhe)


def I(regra: str, msg: str, detalhe: str = "") -> Verificacao:
    return Verificacao(regra, "INFO", "info", msg, detalhe)


# ─────────────────────────────────────────────────────────────────────────────
# Validadores estruturais (CPF / CNPJ)
# ─────────────────────────────────────────────────────────────────────────────

def validar_cpf(cpf: str) -> bool:
    """Valida dígitos verificadores de CPF (algoritmo oficial)."""
    d = so_digitos(cpf)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        resto = soma % 11
        dv = 0 if resto < 2 else 11 - resto
        if dv != int(d[n]):
            return False
    return True


def validar_cnpj(cnpj: str) -> bool:
    """Valida dígitos verificadores de CNPJ (algoritmo oficial)."""
    d = so_digitos(cnpj)
    if len(d) != 14 or d == d[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    resto = sum(int(d[i]) * pesos1[i] for i in range(12)) % 11
    dv1 = 0 if resto < 2 else 11 - resto
    if dv1 != int(d[12]):
        return False
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    resto = sum(int(d[i]) * pesos2[i] for i in range(13)) % 11
    dv2 = 0 if resto < 2 else 11 - resto
    return dv2 == int(d[13])


# ─────────────────────────────────────────────────────────────────────────────
# Regras
# ─────────────────────────────────────────────────────────────────────────────

def regra_cpf(campos, _cadastro=None) -> list[Verificacao]:
    c = campo(campos, "cpf")
    if not c:
        return [I("cpf", "CPF não identificado no documento.", "campo ausente")]
    ok = validar_cpf(c.valor)
    if ok:
        return [P("cpf", f"CPF {c.valor} com dígitos verificadores válidos.")]
    return [F("cpf", f"CPF {c.valor} INVÁLIDO — dígitos verificadores não conferem.",
              "Fortíssimo indicador de documento adulterado ou criado artificialmente.")]


def regra_cnpj(campos, _cadastro=None) -> list[Verificacao]:
    c = campo(campos, "cnpj")
    if not c:
        return [I("cnpj", "CNPJ não identificado no documento.", "campo ausente")]
    ok = validar_cnpj(c.valor)
    if ok:
        return [P("cnpj", f"CNPJ {c.valor} com dígitos verificadores válidos.")]
    return [F("cnpj", f"CNPJ {c.valor} INVÁLIDO — dígitos verificadores não conferem.",
              "Padrão comum em notas fiscais falsas.")]


_RG = re.compile(r"^\d{1,2}\.?\d{3}\.?\d{3}(-?\d{1,2})?$")
_PLACA_MERCOSUL = re.compile(r"^[A-Z]{3}\d[A-Z0-9]\d{2}$")
_PLACA_ANTIGA = re.compile(r"^[A-Z]{3}-?\d{4}$")
_CEP = re.compile(r"^\d{5}-?\d{3}$")


def regra_formatos(campos, _cadastro=None) -> list[Verificacao]:
    saida: list[Verificacao] = []
    if c := campo(campos, "rg"):
        saida.append(P("rg_fmt", f"RG {c.valor} em formato válido.") if _RG.match(c.valor)
                     else W("rg_fmt", f"RG {c.valor} fora do padrão esperado.", "confira digitação/OCR"))
    if c := campo(campos, "cnh"):
        saida.append(P("cnh_fmt", f"CNH com 11 dígitos (não validamos o dígito interno).") if so_digitos(c.valor) and len(so_digitos(c.valor)) == 11
                     else W("cnh_fmt", f"CNH {c.valor} não tem 11 dígitos."))
    if c := campo(campos, "cep"):
        saida.append(P("cep_fmt", f"CEP {c.valor} válido.") if _CEP.match(c.valor)
                     else W("cep_fmt", f"CEP {c.valor} fora do padrão XXXXX-XXX."))
    if c := campo(campos, "placa"):
        ok = bool(_PLACA_MERCOSUL.match(c.valor) or _PLACA_ANTIGA.match(c.valor))
        saida.append(P("placa_fmt", f"Placa {c.valor} válida (padrão Mercosul ou antigo).") if ok
                     else W("placa_fmt", f"Placa {c.valor} em formato suspeito."))
    return saida


def regra_datas(campos, _cadastro=None) -> list[Verificacao]:
    """Validez e ordenação temporal dos campos de data."""
    saida: list[Verificacao] = []
    from datetime import date

    nasc = campo(campos, "nascimento")
    emiss = campo(campos, "emissao")
    validade = campo(campos, "validade")
    venc = campo(campos, "vencimento")

    d_nasc = parse_data(nasc.valor) if nasc else None
    d_emiss = parse_data(emiss.valor) if emiss else None
    d_val = parse_data(validade.valor) if validade else None
    d_venc = parse_data(venc.valor) if venc else None

    if d_nasc and d_nasc > date.today():
        saida.append(F("data_nasc_futuro", f"Data de nascimento {nasc.valor} está no FUTURO.",
                       "Documento com data impossível — adulteração quase certa."))
    if d_nasc and d_nasc.year < 1900:
        saida.append(W("data_nasc_antiga", f"Data de nascimento {nasc.valor} muito antiga.", "confira"))

    if d_nasc and d_emiss and d_emiss < d_nasc:
        saida.append(F("data_ordem", f"Emissão {emiss.valor} anterior ao nascimento {nasc.valor}.",
                       "Ordem cronológica impossível."))

    if d_val:
        if d_val < date.today():
            saida.append(F("validade_expirada", f"Documento com validade EXPIRADA em {validade.valor}.",
                           "Documento vencido não pode ser aceito em processos sensíveis."))
        else:
            saida.append(P("validade", f"Documento válido até {validade.valor}."))

    if d_venc and d_venc < date.today():
        saida.append(F("vencimento_vencido", f"Título VENCIDO em {venc.valor}.", "boleto/duplicata vencida"))
    elif d_venc:
        saida.append(P("vencimento", f"Vencimento {venc.valor} dentro do prazo."))

    if not (nasc or emiss or validade or venc):
        saida.append(I("datas", "Nenhum campo de data identificado.", "impossível validar cronologia"))
    return saida


def regra_consistencia_cadastro(campos, cadastro: dict | None) -> list[Verificacao]:
    """Cruza campos do documento com a base de cadastro (quando fornecida)."""
    if not cadastro:
        return [I("cadastro", "Base de cadastro não fornecida — pulando cruzamento.",
                  "passe --cadastro cadastro.json para ativar")]
    saida: list[Verificacao] = []

    cpf_c = campo(campos, "cpf")
    nome_c = campo(campos, "nome")
    cliente = None
    if cpf_c:
        cliente = cadastro.get(so_digitos(cpf_c.valor))
        if cliente:
            _marca_doc_encontrado(saida, cliente)
        else:
            saida.append(W("cadastro_cpf", f"CPF {cpf_c.valor} NÃO localizado na base de cadastro.",
                           "documento de pessoa sem registro prévio — exige diligência manual"))

    if nome_c and cpf_c and cliente and cliente.get("nome"):
        nome_doc = normalizar_nome(nome_c.valor)
        nome_base = normalizar_nome(cliente["nome"])
        raz = SequenceMatcher(None, nome_doc, nome_base).ratio()
        if raz >= 0.8:
            saida.append(P("cadastro_nome", f"Nome no documento confere com cadastro ({raz:.0%})."))
        else:
            saida.append(F("cadastro_nome",
                           f"Nome no documento '{nome_c.valor}' NÃO confere com cadastro '{cliente['nome']}' ({raz:.0%}).",
                           "Possível uso de documento de terceiros."))
    return saida


def _marca_doc_encontrado(saida: list, cliente: dict) -> None:
    saida.append(P("cadastro_cpf", f"CPF localizado na base: {cliente.get('nome', '?')}."))


def regra_valores(campos, _cadastro=None) -> list[Verificacao]:
    saida: list[Verificacao] = []
    total_c = campo(campos, "total")
    if total_c:
        try:
            total = float(total_c.valor.replace(".", "").replace(",", "."))
        except ValueError:
            return [W("valor_total", f"Total '{total_c.valor}' não é numérico.", "confira OCR")]
        if total <= 0:
            saida.append(F("valor_total", f"Total {total_c.valor} não é positivo.", "valor impossível"))
        else:
            br = f"{total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            saida.append(P("valor_total", f"Total de R$ {br} positivo e razoável."))
    return saida


def regra_total_vs_itens(campos, _cadastro=None) -> list[Verificacao]:
    """Soma dos itens deve bater com o total da nota."""
    itens = [c for c in campos if c.nome.startswith("item")]
    total_c = campo(campos, "total")
    if not itens or not total_c:
        return [I("total_itens", "Sem itens+total para conferência.", "não aplicável")]
    try:
        soma = sum(float(c.valor.replace(".", "").replace(",", ".")) for c in itens)
        total = float(total_c.valor.replace(".", "").replace(",", "."))
    except ValueError:
        return [W("total_itens", "Não foi possível somar itens.", "erro de parse")]
    if abs(soma - total) > 0.02:
        return [F("total_itens", f"Soma dos itens ({soma:,.2f}) ≠ Total da nota ({total:,.2f}).".replace(",", "X").replace(".", ",").replace("X", "."),
                  "Divergência clássica em nota fiscal adulterada.")]
    return [P("total_itens", f"Soma dos itens confere com o total ({total:,.2f}).".replace(",", "X").replace(".", ",").replace("X", "."))]


def regra_confianca_ocr(campos, extracao=None) -> list[Verificacao]:
    saida: list[Verificacao] = []
    if extracao and extracao.confianca_media < 0.7:
        saida.append(W("ocr_confianca", f"Confiança média do OCR baixa ({extracao.confianca_media:.0%}).",
                       "Qualidade de imagem pode estar degradada de propósito."))
    essenciais = [c for c in campos if c.confianca < 0.55]
    for c in essenciais:
        saida.append(W("ocr_campo_baixo", f"Campo '{c.nome}' com confiança de apenas {c.confianca:.0%}.",
                       "OCR inseguro em campo crítico."))
    return saida


def regra_campos_obrigatorios(campos, tipo: str | None = None) -> list[Verificacao]:
    """Documento deve conter os campos mínimos do tipo declarado."""
    obrigatorios = {
        "rg": ["nome", "cpf", "rg", "nascimento", "emissao"],
        "cnh": ["nome", "cnh", "nascimento"],
        "nf": ["cnpj", "total", "emissao"],
        "boleto": ["valor", "vencimento", "nome"],
        "comprovante": ["nome", "cep", "endereco"],
    }
    chaves = {c.nome for c in campos}
    faltando = [k for k in obrigatorios.get(tipo or "", []) if k not in chaves]
    if not faltando:
        return [P("campos_min", f"Documento {tipo.upper()} com todos os campos obrigatórios.")]
    return [F("campos_min", f"Faltam campos essenciais para {tipo.upper()}: {', '.join(faltando)}.",
              "Documento incompleto — comum em montagens fraudulentas.")]


def regra_hash(arquivo: str, armadilha_duplicados: set | None) -> list[Verificacao]:
    from .models import hash_arquivo
    h = hash_arquivo(arquivo)
    if armadilha_duplicados:
        if h in armadilha_duplicados:
            return [W("duplicidade", "Hash do arquivo já foi analisado nesta sessão.",
                      f"SHA-256 {h[:16]}… — reenvio do mesmo arquivo suspeito")]
        armadilha_duplicados.add(h)
        return [I("duplicidade", "Hash do arquivo único nesta sessão.", f"SHA-256 {h[:16]}…")]
    return [I("duplicidade", f"Hash do arquivo: SHA-256 {h[:16]}…", "use no rastreio de reenvios")]


# ─────────────────────────────────────────────────────────────────────────────
# Orquestração
# ─────────────────────────────────────────────────────────────────────────────

REGRAS_POR_TIPO = {
    "rg": [regra_cpf, regra_formatos, regra_datas, regra_consistencia_cadastro,
           regra_confianca_ocr, regra_campos_obrigatorios, regra_hash],
    "cnh": [regra_cpf, regra_formatos, regra_datas, regra_consistencia_cadastro,
            regra_confianca_ocr, regra_campos_obrigatorios, regra_hash],
    "nf": [regra_cnpj, regra_datas, regra_valores, regra_total_vs_itens,
           regra_consistencia_cadastro, regra_confianca_ocr, regra_campos_obrigatorios, regra_hash],
    "boleto": [regra_datas, regra_valores, regra_consistencia_cadastro,
               regra_confianca_ocr, regra_campos_obrigatorios, regra_hash],
    "comprovante": [regra_formatos, regra_consistencia_cadastro,
                    regra_confianca_ocr, regra_campos_obrigatorios, regra_hash],
}

TIPOS_VALIDOS = sorted(REGRAS_POR_TIPO)


def aplicar_regras(campos, tipo: str | None, arquivo: str,
                   cadastro: dict | None = None, extracao=None,
                   armadilha_duplicados: set | None = None) -> list[Verificacao]:
    """Roda o conjunto de regras do tipo de documento."""
    regras = REGRAS_POR_TIPO.get(tipo or "", [])
    if not regras:
        regras = [regra_cpf, regra_cnpj, regra_formatos, regra_datas,
                  regra_valores, regra_total_vs_itens, regra_consistencia_cadastro,
                  regra_confianca_ocr, regra_hash]
    saida: list[Verificacao] = []
    for regra in regras:
        if regra is regra_hash:
            saida.extend(regra(arquivo, armadilha_duplicados))
        elif regra is regra_campos_obrigatorios:
            saida.extend(regra(campos, tipo))
        elif regra is regra_confianca_ocr:
            saida.extend(regra(campos, extracao))
        elif regra is regra_consistencia_cadastro:
            saida.extend(regra(campos, cadastro))
        else:
            saida.extend(regra(campos, cadastro))
    return saida