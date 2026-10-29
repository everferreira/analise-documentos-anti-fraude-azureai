/* ═══════════════════════════════════════════════════════════════════════
   DocShield AI — Análise anti-fraude de documentos no navegador
   Motor JS espelha src/anti_fraude/*.py (mesmas regras, pesos e thresholds).
   OCR: Tesseract.js auto-hospedado (vendor/) — sem dependência de CDN, offline.
   ═══════════════════════════════════════════════════════════════════════ */

"use strict";

/* ─── Paths do Tesseract.js (self-hosted — tudo em vendor/) ─── */
if (typeof Tesseract !== "undefined") {
  Tesseract.workerPath = "vendor/worker.min.js";
  Tesseract.corePath = "vendor/tesseract-core-simd.wasm.js";
  Tesseract.langPath = "vendor/tessdata";
}

/* ───────────────────────── Utilidades ───────────────────────── */
const soDigitos = (v) => (v || "").replace(/\D/g, "");
const normalizarNome = (v) =>
  (v || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase().replace(/\s+/g, " ").trim();

function parseData(v) {
  const m = (v || "").match(/(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})/);
  if (!m) return null;
  let [, d, mes, ano] = m.map(Number);
  if (ano < 100) ano += ano <= 40 ? 2000 : 1900;
  const dt = new Date(ano, mes - 1, d);
  return dt.getFullYear() === ano && dt.getMonth() === mes - 1 && dt.getDate() === d ? dt : null;
}
const hoje = () => { const x = new Date(); return new Date(x.getFullYear(), x.getMonth(), x.getDate()); };

/* ─────────────── Validação CPF / CNPJ (oficiais) ─────────────── */
function validarCpf(cpf) {
  const d = soDigitos(cpf);
  if (d.length !== 11 || /^(\d)\1{10}$/.test(d)) return false;
  for (const n of [9, 10]) {
    let soma = 0;
    for (let i = 0; i < n; i++) soma += +d[i] * (n + 1 - i);
    const dv = soma % 11 < 2 ? 0 : 11 - (soma % 11);
    if (dv !== +d[n]) return false;
  }
  return true;
}

function validarCnpj(cnpj) {
  const d = soDigitos(cnpj);
  if (d.length !== 14 || /^(\d)\1{13}$/.test(d)) return false;
  const p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  let r = 0; for (let i = 0; i < 12; i++) r += +d[i] * p1[i];
  const dv1 = r % 11 < 2 ? 0 : 11 - (r % 11);
  if (dv1 !== +d[12]) return false;
  const p2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  r = 0; for (let i = 0; i < 13; i++) r += +d[i] * p2[i];
  const dv2 = r % 11 < 2 ? 0 : 11 - (r % 11);
  return dv2 === +d[13];
}

/* similaridade entre nomes (LCS → ratio, como difflib.SequenceMatcher) */
function simil(a, b) {
  a = normalizarNome(a); b = normalizarNome(b);
  if (!a.length || !b.length) return 0;
  const dp = Array.from({ length: a.length + 1 }, () => new Array(b.length + 1).fill(0));
  for (let i = 1; i <= a.length; i++)
    for (let j = 1; j <= b.length; j++)
      dp[i][j] = a[i - 1] === b[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1]);
  const lcs = dp[a.length][b.length];
  return (2 * lcs) / (a.length + b.length);
}

/* ─────────────────────── Parser de campos ─────────────────────── */
const RE_CPF = /\b(\d{3}\.\d{3}\.\d{3}-\d{2})\b/;
const RE_CNPJ = /\b(\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2})\b/;
const RE_RG = /\b(\d{1,2}\.?\d{3}\.?\d{3}-?\d{1,2})\b/;
const RE_DATA = /\b(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})\b/g;
const RE_VALOR = /(?:\$\s?)?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})/g;
const RE_CEP = /\b(\d{5}-?\d{3})\b/;
const RE_CNH = /\b(\d{11})\b/;

const ROTULO_DATA = {
  nascimento: /(?:NASCIMENTO|NASC|DATA\s+DE\s+NASCIMENTO|\bDN\b)/,
  emissao: /(?:EMISS[ÃA]O|DATA\s+(?:DE\s+)?EMISS[ÃA]O|EXPEDI[ÇC][ÃA]O|EMITIDO\s+EM)/,
  validade: /(?:VALIDADE|VALIDO\s+ATE|EXPIRA)/,
  vencimento: /(?:VENCIMENTO|VENCE|PAGAVEL\s+ATE)/,
};
const ROTULO_NOME = /(?:NOME|CLIENTE|FAVORECIDO|BENEFICI[ÁA]RIO|TITULAR|SACADO)/;
const ROTULO_ENDERECO = /(?:ENDERE[ÇC]O|RUA|AVENIDA|LOGRADOURO|\bAV\b)/;
const APARAR_NOME = /\s+(?:CPF|FILIACAO|RG\b|NASCIMENTO|EMISSAO|VALIDADE|ENDERECO|CEP|ITENS)\b/;

const txtNorm = (t) => (t || "").toUpperCase().replace(/\s+/g, " ");

function parseCampos(texto, tipo) {
  const t = txtNorm(texto);
  const campos = [];
  const add = (nome, valor) => {
    if (!valor) return;
    if (!campos.some((c) => c.nome === nome && c.valor === valor)) campos.push({ nome, valor });
  };
  const campoNome = (n) => campos.find((c) => c.nome === n);

  if (["", "rg", "cnh", "comprovante"].includes(tipo)) {
    const cpf = t.match(RE_CPF); if (cpf) add("cpf", cpf[1]);
    const cnh = t.match(RE_CNH); if (cnh) add("cnh", cnh[1]);
    if (["rg", "cnh"].includes(tipo) || /REGISTRO\s+GERAL/.test(t) || /\bRG\b/.test(t)) {
      const rg = t.match(/REGISTRO\s+GERAL\s*[:.\-]?\s*(\d{1,2}\.?\d{3}\.?\d{3}-?\d{1,2})/) || t.match(RE_RG);
      if (rg) add("rg", rg[1]);
    }
  }
  if (["", "nf", "boleto"].includes(tipo)) {
    const cnpj = t.match(RE_CNPJ); if (cnpj) add("cnpj", cnpj[1]);
  }
  if (["", "rg", "cnh", "boleto", "comprovante"].includes(tipo)) {
    const m = t.match(new RegExp(ROTULO_NOME.source + "\\s*[:;.\\-]?\\s*([A-ZÀ-Ú][A-ZÀ-Ú\\s.'\\-]{4,60})"));
    if (m) {
      let nome = m[1].trim().split(APARAR_NOME)[0].trim();
      add("nome", nome);
    }
  }
  for (const [rotulo, padrao] of Object.entries(ROTULO_DATA)) {
    const m = t.match(new RegExp(padrao.source + "\\s*[:;.\\-]?\\s*(\\d{1,2}[/\\-.]\\d{1,2}[/\\-.]\\d{2,4})"));
    if (m) add(rotulo, m[1]);
  }
  if (["rg", "cnh"].includes(tipo)) {
    const datas = t.match(RE_DATA) || [];
    if (datas[0] && !campoNome("nascimento")) add("nascimento", datas[0]);
    if (datas[1] && !campoNome("emissao")) add("emissao", datas[1]);
  }
  if (["", "comprovante"].includes(tipo)) {
    const end = t.match(new RegExp(ROTULO_ENDERECO.source + "\\s*[:;.\\-]?\\s*([A-Z0-9À-Ú.,\\s/\\-]{5,60})"));
    if (end) add("endereco", end[1].trim());
    const cep = t.match(RE_CEP); if (cep) add("cep", cep[1]);
  }
  if (["", "nf", "boleto"].includes(tipo)) {
    const mv = t.match(/(TOTAL|VALOR)\s*[:;.\-]?\s*R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})/);
    if (mv) add(mv[1] === "TOTAL" ? "total" : "valor", mv[2]);
    else if (tipo !== "boleto") {
      const vals = [...t.matchAll(RE_VALOR)].map((m) => m[1]);
      if (vals.length) add("total", vals[vals.length - 1]);
    }
    if (tipo === "nf") {
      const total = campoNome("total");
      for (const v of t.matchAll(RE_VALOR)) {
        if (total && v[1] === total.valor) continue;
        if (!campos.some((c) => c.nome.startsWith("item") && c.valor === v[1]))
          add("item" + (campos.filter((c) => c.nome.startsWith("item")).length + 1), v[1]);
      }
    }
    if (tipo === "boleto" && !campoNome("total")) {
      const v = campoNome("valor");
      if (v) add("total", v.valor);
    }
  }
  return campos;
}

/* ─────────────────────── Motor de regras ─────────────────────── */
const P = (regra, mensagem, detalhe = "") => ({ regra, status: "PASS", severidade: "info", mensagem, detalhe });
const F = (regra, mensagem, detalhe = "", severidade = "critical") => ({ regra, status: "FAIL", severidade, mensagem, detalhe });
const W_ = (regra, mensagem, detalhe = "") => ({ regra, status: "WARN", severidade: "warn", mensagem, detalhe });
const I_ = (regra, mensagem, detalhe = "") => ({ regra, status: "INFO", severidade: "info", mensagem, detalhe });

function campo(campos, nome) { return campos.find((c) => c.nome === nome); }
function br(v) { return v.toFixed(2).replace(/\./g, ","); }

function regraCpf(campos) {
  const c = campo(campos, "cpf");
  if (!c) return [I_("cpf", "CPF não identificado no documento.", "campo ausente")];
  return validarCpf(c.valor)
    ? [P("cpf", `CPF ${c.valor} com dígitos verificadores válidos.`)]
    : [F("cpf", `CPF ${c.valor} INVÁLIDO — dígitos verificadores não conferem.`, "Fortíssimo indicador de documento adulterado ou criado artificialmente.")];
}
function regraCnpj(campos) {
  const c = campo(campos, "cnpj");
  if (!c) return [I_("cnpj", "CNPJ não identificado no documento.", "campo ausente")];
  return validarCnpj(c.valor)
    ? [P("cnpj", `CNPJ ${c.valor} com dígitos verificadores válidos.`)]
    : [F("cnpj", `CNPJ ${c.valor} INVÁLIDO — dígitos verificadores não conferem.`, "Padrão comum em notas fiscais falsas.")];
}
function regraFormatos(campos) {
  const saida = [];
  const rg = campo(campos, "rg");
  if (rg) saida.push(/^\d{1,2}\.?\d{3}\.?\d{3}-?\d{1,2}$/.test(rg.valor)
    ? P("rg_fmt", `RG ${rg.valor} em formato válido.`)
    : W_("rg_fmt", `RG ${rg.valor} fora do padrão esperado.`, "confira digitação/OCR"));
  const cnh = campo(campos, "cnh");
  if (cnh) saida.push(soDigitos(cnh.valor).length === 11
    ? P("cnh_fmt", "CNH com 11 dígitos (dígito interno não validado).")
    : W_("cnh_fmt", `CNH ${cnh.valor} não tem 11 dígitos.`));
  const cep = campo(campos, "cep");
  if (cep) saida.push(/^\d{5}-?\d{3}$/.test(cep.valor)
    ? P("cep_fmt", `CEP ${cep.valor} válido.`)
    : W_("cep_fmt", `CEP ${cep.valor} fora do padrão XXXXX-XXX.`));
  return saida;
}
function regraDatas(campos) {
  const saida = [];
  const d = (n) => { const c = campo(campos, n); return c ? parseData(c.valor) : null; };
  const nasc = d("nascimento"), emiss = d("emissao"), val = d("validade"), venc = d("vencimento");
  const hj = hoje();
  if (nasc && nasc > hj) saida.push(F("data_nasc_futuro", `Data de nascimento ${campo(campos, "nascimento").valor} está no FUTURO.`, "Documento com data impossível — adulteração quase certa."));
  if (nasc && emiss && emiss < nasc) saida.push(F("data_ordem", `Emissão ${campo(campos, "emissao").valor} anterior ao nascimento ${campo(campos, "nascimento").valor}.`, "Ordem cronológica impossível."));
  if (val) saida.push(val < hj
    ? F("validade_expirada", `Documento com validade EXPIRADA em ${campo(campos, "validade").valor}.`, "Documento vencido não pode ser aceito em processos sensíveis.")
    : P("validade", `Documento válido até ${campo(campos, "validade").valor}.`));
  if (venc) saida.push(venc < hj
    ? F("vencimento_vencido", `Título VENCIDO em ${campo(campos, "vencimento").valor}.`, "boleto/duplicata vencida")
    : P("vencimento", `Vencimento ${campo(campos, "vencimento").valor} dentro do prazo.`));
  if (!nasc && !emiss && !val && !venc) saida.push(I_("datas", "Nenhum campo de data identificado.", "impossível validar cronologia"));
  return saida;
}
function regraCadastro(campos, cadastro) {
  if (!cadastro) return [I_("cadastro", "Base de cadastro não fornecida — pulando cruzamento.", "ative a opção 'Cruzamento com cadastro'")];
  const saida = [];
  const cpfC = campo(campos, "cpf"), nomeC = campo(campos, "nome");
  let cliente = null;
  if (cpfC) {
    cliente = cadastro[soDigitos(cpfC.valor)];
    if (cliente) saida.push(P("cadastro_cpf", `CPF localizado na base: ${cliente.nome}.`));
    else saida.push(W_("cadastro_cpf", `CPF ${cpfC.valor} NÃO localizado na base de cadastro.`, "documento de pessoa sem registro prévio — exige diligência manual"));
  }
  if (nomeC && cpfC && cliente && cliente.nome) {
    const raz = simil(nomeC.valor, cliente.nome);
    saida.push(raz >= 0.8
      ? P("cadastro_nome", `Nome no documento confere com cadastro (${Math.round(raz * 100)}%).`)
      : F("cadastro_nome", `Nome no documento '${nomeC.valor}' NÃO confere com cadastro '${cliente.nome}' (${Math.round(raz * 100)}%).`, "Possível uso de documento de terceiros."));
  }
  return saida;
}
function regraValores(campos) {
  const saida = [];
  const totalC = campo(campos, "total") || campo(campos, "valor");
  if (!totalC) return saida;
  const v = parseFloat(totalC.valor.replace(/\./g, "").replace(",", "."));
  if (isNaN(v)) return [W_("valor_total", `Total '${totalC.valor}' não é numérico.`, "confira OCR")];
  saida.push(v <= 0
    ? F("valor_total", `Total ${totalC.valor} não é positivo.`, "valor impossível")
    : P("valor_total", `Total de R$ ${br(v)} positivo e razoável.`));
  return saida;
}
function regraTotalItens(campos) {
  const itens = campos.filter((c) => c.nome.startsWith("item"));
  const totalC = campo(campos, "total");
  if (!itens.length || !totalC) return [I_("total_itens", "Sem itens+total para conferência.", "não aplicável")];
  const num = (s) => parseFloat(s.replace(/\./g, "").replace(",", "."));
  const soma = itens.reduce((a, c) => a + num(c.valor), 0);
  const total = num(totalC.valor);
  return Math.abs(soma - total) > 0.02
    ? [F("total_itens", `Soma dos itens (${br(soma)}) ≠ Total da nota (${br(total)}).`, "Divergência clássica em nota fiscal adulterada.")]
    : [P("total_itens", `Soma dos itens confere com o total (${br(total)}).`)];
}
function regraConfianca(campos, extracao) {
  const saida = [];
  if (extracao && extracao.confiancaMedia < 0.7)
    saida.push(W_("ocr_confianca", `Confiança média do OCR baixa (${Math.round(extracao.confiancaMedia * 100)}%).`, "Qualidade de imagem pode estar degradada de propósito."));
  return saida;
}
const OBRIGATORIOS = {
  rg: ["nome", "cpf", "rg", "nascimento", "emissao"],
  cnh: ["nome", "cnh", "nascimento"],
  nf: ["cnpj", "total", "emissao"],
  boleto: ["valor", "vencimento", "nome"],
  comprovante: ["nome", "cep", "endereco"],
};
function regraCamposMin(campos, tipo) {
  const chaves = new Set(campos.map((c) => c.nome));
  const faltando = (OBRIGATORIOS[tipo] || []).filter((k) => !chaves.has(k));
  if (!faltando.length) return [P("campos_min", `Documento ${tipo.toUpperCase()} com todos os campos obrigatórios.`)];
  return [F("campos_min", `Faltam campos essenciais para ${tipo.toUpperCase()}: ${faltando.join(", ")}.`, "Documento incompleto — comum em montagens fraudulentas.")];
}

function aplicarRegras(campos, tipo, cadastro, extracao) {
  const regras = {
    rg: [regraCpf, regraFormatos, regraDatas, regraCadastro, regraConfianca, regraCamposMin],
    cnh: [regraCpf, regraFormatos, regraDatas, regraCadastro, regraConfianca, regraCamposMin],
    nf: [regraCnpj, regraDatas, regraValores, regraTotalItens, regraCadastro, regraConfianca, regraCamposMin],
    boleto: [regraDatas, regraValores, regraCadastro, regraConfianca, regraCamposMin],
    comprovante: [regraFormatos, regraCadastro, regraConfianca, regraCamposMin],
  }[tipo] || [];
  const saida = [];
  for (const fn of regras) {
    if (fn === regraCamposMin) saida.push(...fn(campos, tipo));
    else if (fn === regraConfianca) saida.push(...fn(campos, extracao));
    else saida.push(...fn(campos, cadastro || null));
  }
  return saida;
}

/* ───────────────────────── Score ───────────────────────── */
const PESO = { info: 0, warn: 12, critical: 30 };

function calcularScore(verificacoes) {
  return Math.min(100, verificacoes.reduce((a, v) => a + (v.status === "FAIL" || v.status === "WARN" ? PESO[v.severidade] : 0), 0));
}
function classificar(score) { return score < 25 ? "BAIXO" : score < 55 ? "MEDIO" : "ALTO"; }
function parecer(verificacoes) {
  if (verificacoes.some((v) => v.status === "FAIL" && v.severidade === "critical")) return "REPROVADO";
  if (verificacoes.some((v) => v.status === "WARN")) return "APROVADO COM RESSALVAS";
  return "APROVADO";
}

function analisar(texto, tipo, nomeArquivo, cadastro, extracao) {
  const campos = parseCampos(texto, tipo);
  const verificacoes = aplicarRegras(campos, tipo, cadastro, extracao);
  const score = calcularScore(verificacoes);
  return { arquivo: nomeArquivo, tipo, campos, verificacoes, score, classificacao: classificar(score), parecer: parecer(verificacoes), extracao };
}

/* ─────────────────── Catálogo e dados estáticos ─────────────────── */
const AMOSTRAS = [
  { arquivo: "rg_ok.png", tipo: "rg", rotulo: "RG válido", suspeita: false },
  { arquivo: "rg_adulterado.png", tipo: "rg", rotulo: "RG adulterado", suspeita: true },
  { arquivo: "nf_ok.png", tipo: "nf", rotulo: "NF válida", suspeita: false },
  { arquivo: "nf_suspeita.png", tipo: "nf", rotulo: "NF suspeita", suspeita: true },
  { arquivo: "boleto_ok.png", tipo: "boleto", rotulo: "Boleto válido", suspeita: false },
  { arquivo: "comprovante_inconsistente.png", tipo: "comprovante", rotulo: "Comprovante inconsistente", suspeita: true },
];

const CADASTRO = {
  "10433218100": { nome: "JOAO PEREIRA DA SILVA", cidade: "SAO PAULO", observacao: "cliente desde 2019" },
};

/* extrações de referência (fallback quando OCR desligado/indisponível;
   geradas por scripts/gerar_amostras.py — espelham o que o OCR lê) */
const REFERENCIA = {
  "rg_ok.png": { tipo: "rg", texto: "REGISTRO GERAL (RG)\nNOME: JOAO PEREIRA DA SILVA\nFILIACAO: CARLOS PEREIRA DA SILVA / MARIA HELENA SOUZA\nREGISTRO GERAL: 12.345.678-9\nORGAO EMISSOR: SSP/SP\nCPF: 104.332.181-00\nNASCIMENTO: 15/03/1990\nEMISSAO: 10/01/2024\nVALIDADE: 10/01/2034", confiancaMedia: 0.98, provedor: "referência" },
  "rg_adulterado.png": { tipo: "rg", texto: "REGISTRO GERAL (RG)\nNOME: JOAO PEREIRA DA SILVA\nFILIACAO: CARLOS PEREIRA DA SILVA / MARIA HELENA SOUZA\nREGISTRO GERAL: 12.345.678-9\nORGAO EMISSOR: SSP/SP\nCPF: 104.332.181-01\nNASCIMENTO: 15/03/1990\nEMISSAO: 10/01/2024\nVALIDADE: 10/01/2025", confiancaMedia: 0.98, provedor: "referência" },
  "nf_ok.png": { tipo: "nf", texto: "NOTA FISCAL DE VENDA Nº 000123\nEMITENTE: COMERCIO DE MATERIAIS XYZ LTDA\nCNPJ: 96.001.338/0001-37\nDATA EMISSAO: 05/05/2026\nITENS:\nCANETA ESFEROGRÁFICA .......... R$ 10,00\nCADERNO 96 FOLHAS ............... R$ 25,50\nMOCHILA ESCOLAR ................. R$ 89,90\nTOTAL: R$ 125,40", confiancaMedia: 0.98, provedor: "referência" },
  "nf_suspeita.png": { tipo: "nf", texto: "NOTA FISCAL DE VENDA Nº 000124\nEMITENTE: COMERCIO DE MATERIAIS XYZ LTDA\nCNPJ: 96.001.338/0001-38\nDATA EMISSAO: 05/05/2026\nITENS:\nCANETA ESFEROGRÁFICA .......... R$ 10,00\nCADERNO 96 FOLHAS ............... R$ 25,50\nMOCHILA ESCOLAR ................. R$ 89,90\nTOTAL: R$ 155,40", confiancaMedia: 0.98, provedor: "referência" },
  "boleto_ok.png": { tipo: "boleto", texto: "BOLETO DE COBRANCA\nFAVORECIDO: EMPRESA DE ENERGIA SA\nSACADO: JOAO PEREIRA DA SILVA\nVALOR: R$ 187,42\nVENCIMENTO: 20/11/2026\nLINHA DIGITAVEL: 23793.38128 60007.827113 95000.063305 7 83690000018742", confiancaMedia: 0.98, provedor: "referência" },
  "comprovante_inconsistente.png": { tipo: "comprovante", texto: "COMPROVANTE DE RESIDENCIA\nNOME: CARLOS ALBERTO DE SOUZA\nCPF: 104.332.181-00\nENDERECO: RUA DAS FLORES, 123 - SAO PAULO/SP\nCEP: 01234-567\nDATA EMISSAO: 01/08/2026", confiancaMedia: 0.98, provedor: "referência" },
};

/* ───────────────────────── UI ───────────────────────── */
const $ = (id) => document.getElementById(id);
const dropzone = $("dropzone"), arquivoInput = $("arquivo"), relatorio = $("relatorio");

function mostraProgresso(texto, pct) {
  $("progresso").hidden = false;
  $("progresso-fill").style.width = (pct * 100).toFixed(0) + "%";
  $("progresso-texto").textContent = texto;
}
function escondeProgresso() { $("progresso").hidden = true; }
function mostraErro(msg) { const e = $("erro"); e.textContent = msg; e.hidden = false; }
function escondeErro() { $("erro").hidden = true; }

async function sha256(file) {
  const buf = await file.arrayBuffer();
  const d = await crypto.subtle.digest("SHA-256", buf);
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

const CORES = { BAIXO: "#22c55e", MEDIO: "#f59e0b", ALTO: "#ef4444" };
const SIMB = { PASS: "✅", FAIL: "❌", WARN: "⚠️", INFO: "ℹ️" };

function renderRelatorio(r, hash, metaExtra) {
  relatorio.hidden = false;
  relatorio.scrollIntoView({ behavior: "smooth", block: "nearest" });
  $("rel-arquivo").textContent = "📄 " + r.arquivo;
  const tipoLbl = r.tipo ? r.tipo.toUpperCase() : "AUTO";
  $("rel-meta").textContent = `${tipoLbl} · ${r.extracao.provedor} · confiança OCR ${Math.round((r.extracao.confiancaMedia || 1) * 100)}%${metaExtra ? " · " + metaExtra : ""}`;

  const circ = 2 * Math.PI * 52;
  const fill = $("gauge-fill");
  fill.style.stroke = CORES[r.classificacao];
  fill.style.strokeDasharray = circ;
  fill.style.strokeDashoffset = circ * (1 - r.score / 100);
  $("gauge-num").textContent = r.score;

  const seloRisco = $("selo-risco");
  seloRisco.textContent = "RISCO " + r.classificacao;
  seloRisco.className = "selo selo-risco b" + r.classificacao;
  const seloParecer = $("selo-parecer");
  seloParecer.textContent = r.parecer;
  seloParecer.className = "selo selo-parecer";

  const camposEl = $("rel-campos");
  camposEl.innerHTML = "";
  if (!r.campos.length) camposEl.innerHTML = '<p class="campo">Nenhum campo estruturado identificado.</p>';
  for (const c of r.campos) {
    const div = document.createElement("div");
    div.className = "campo" + (c.confianca && c.confianca < 0.55 ? " fraca" : "");
    div.innerHTML = `<b>${c.nome.replace(/^item/, "item ")}</b><span>${c.valor}</span>`;
    camposEl.appendChild(div);
  }

  const checksEl = $("rel-checks");
  checksEl.innerHTML = "";
  for (const v of r.verificacoes) {
    const li = document.createElement("li");
    li.className = "check " + v.status;
    li.innerHTML = `<span class="check-titulo">${SIMB[v.status] || "•"} [${v.regra}] ${v.mensagem}</span>` +
      (v.detalhe ? `<span class="check-det">↳ ${v.detalhe}</span>` : "");
    checksEl.appendChild(li);
  }

  $("rel-hash").textContent = hash
    ? `🔏 SHA-256: ${hash}`
    : "🔏 Hash indisponível (carregue o arquivo para calcular)";
}

function adicionarHistorico(r, hash) {
  const sec = $("historico"), lista = $("historico-lista");
  sec.hidden = false;
  const item = document.createElement("div");
  item.className = "historico-item";
  const cor = CORES[r.classificacao];
  item.innerHTML = `<span class="h-nome">${r.arquivo} <small style="color:var(--texto2)">· ${r.tipo}</small></span>` +
    `<span class="h-score" style="background:${cor}22;color:${cor}">${r.classificacao} · ${r.score}</span>`;
  lista.prepend(item);
}

/* ─────────────────── OCR (Tesseract.js) ─────────────────── */
let workerPromise = null;
function obterWorker() {
  if (!workerPromise) {
    workerPromise = Tesseract.createWorker("por", 1, {
      logger: (m) => {
        if (m.status === "recognizing text")
          mostraProgresso("Reconhecendo texto (OCR local)…", m.progress);
        else if (m.status === "loading tesseract core" || m.status === "initializing tesseract")
          mostraProgresso("Carregando motor OCR…", m.progress || 0.05);
        else if (m.status === "loading language traineddata")
          mostraProgresso("Baixando modelo de português (1ª vez, ~15 MB)…", m.progress || 0.1);
      },
    });
    workerPromise.catch(() => { workerPromise = null; });
  }
  return workerPromise;
}

async function ocrArquivo(file) {
  escondeErro();
  if (typeof Tesseract === "undefined") {
    throw new Error("Motor OCR (Tesseract.js) não carregou. Verifique a internet e recarregue a página.");
  }
  mostraProgresso("Carregando motor OCR…", 0.05);
  const worker = await obterWorker();
  const { data } = await worker.recognize(file);
  return { texto: data.text || "", confiancaMedia: data.confidence ? data.confidence / 100 : 0.9, provedor: "Tesseract.js (OCR local)" };
}

async function analisarArquivo(file, tipo) {
  try {
    escondeErro();
    if (/\.pdf$/i.test(file.name) || file.type === "application/pdf") {
      throw new Error("PDF ainda não é suportado no navegador (o OCR local lê imagens). Converta para PNG/JPG ou use uma amostra abaixo.");
    }
    const usarOcr = $("modo-ocr").checked;
    let extracao = null;
    if (usarOcr) {
      try {
        extracao = await ocrArquivo(file);
      } catch (e) {
        console.warn("OCR falhou:", e);
        extracao = null;
      }
    }
    if (!extracao) {
      const base = REFERENCIA[file.name];
      if (base) {
        extracao = { texto: base.texto, confiancaMedia: base.confiancaMedia, provedor: "referência (demo)" };
        tipo = tipo || base.tipo;
      } else {
        throw new Error(
          (usarOcr
            ? "O OCR local não conseguiu ler este documento (motor indisponível ou imagem ilegível). "
            : "Sem extração disponível para este arquivo. ") +
          "Dicas: use uma imagem nítida (PNG/JPG), ative a opção 'OCR real', ou teste com uma amostra abaixo."
        );
      }
    }
    escondeProgresso();
    const cadastro = $("modo-cadastro").checked ? CADASTRO : null;
    const r = analisar(extracao.texto, tipo || null, file.name, cadastro, extracao);
    r.extracao = extracao;
    let hash = null;
    try { hash = await sha256(file); } catch (e) { /* file:// ou contexto sem subtle */ }
    renderRelatorio(r, hash, usarOcr ? "" : "modo referência (sem OCR)");
    adicionarHistorico(r, hash);
  } catch (e) {
    console.error("Falha na análise:", e);
    escondeProgresso();
    mostrarErro("⚠️ " + (e && e.message ? e.message : "Não foi possível analisar o documento. Tente novamente."));
  }
}

/* ─────────────────── Eventos ─────────────────── */
dropzone.addEventListener("click", () => arquivoInput.click());
dropzone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); arquivoInput.click(); } });
["dragenter", "dragover"].forEach((ev) => dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("dragging"); }));
["dragleave", "drop"].forEach((ev) => dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("dragging"); }));
dropzone.addEventListener("drop", (e) => {
  const f = e.dataTransfer.files[0];
  if (f) analisarArquivo(f, null);
});
arquivoInput.addEventListener("change", () => {
  if (arquivoInput.files[0]) analisarArquivo(arquivoInput.files[0], null);
  arquivoInput.value = "";
});

function montarAmostras() {
  const grid = $("amostras-grid");
  for (const a of AMOSTRAS) {
    const el = document.createElement("div");
    el.className = "amostra" + (a.suspeita ? " suspeita" : "");
    el.title = `Analisar ${a.rotulo}`;
    el.innerHTML = `<img src="samples/${a.arquivo}" alt="${a.rotulo}" loading="lazy">` +
      `<div class="amostra-nome"><span>${a.rotulo}</span><span class="amostra-tipo">${a.tipo}</span></div>`;
    el.addEventListener("click", () => {
      fetch("samples/" + a.arquivo)
        .then((res) => res.blob())
        .then((blob) => analisarArquivo(new File([blob], a.arquivo, { type: blob.type || "image/png" }), a.tipo))
        .catch((e) => mostraErro("Não foi possível carregar a amostra: " + e.message));
    });
    grid.appendChild(el);
  }
}

montarAmostras();

/* exporta motor puro para testes (Node) — inofensivo no navegador */
if (typeof module !== "undefined" && module.exports) {
  module.exports = { analisar, parseCampos, validarCpf, validarCnpj, classificar, parecer, simil, REFERENCIA, AMOSTRAS, CADASTRO };
}