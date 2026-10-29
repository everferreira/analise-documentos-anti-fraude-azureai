# 🛡️ Análise de Documentos Anti-fraude com Azure AI

<p align="center">
<a href="https://dio.me/">
    <img src="https://img.shields.io/badge/DIO-Certification%20IA--102-28DA77?logo=azure" alt="DIO - IA-102">
</a>
<a href="https://github.com/everferreira">
    <img src="https://img.shields.io/badge/Ever%20Ferreira-GitHub-0a1e3d?logo=github" alt="GitHub - Ever Ferreira">
</a>
<img src="https://img.shields.io/badge/Azure%20AI-Document%20Intelligence-0078D4?logo=microsoftazure" alt="Azure AI Document Intelligence">
<img src="https://img.shields.io/badge/OCR-Local%20(rapidocr%20%2F%20tesseract.js)-6a5acd" alt="OCR local">
</p>

<p align="center">
    <a href="https://everferreira.github.io/analise-documentos-anti-fraude-azureai/">
        <strong>▶️ Teste Online — Analise um documento agora</strong>
    </a>
</p>

> ℹ️ **NOTE:** Projeto do desafio **Análise de Documentos Anti-fraude com AzureAI** — certificação **IA-102 (Microsoft Azure AI Solutions)** da [DIO](https://dio.me), com o expert **Henrique Eduardo Souza (Microsoft MVP)**.

Solução de análise automatizada de documentos que identifica **padrões de fraude**, valida **autenticidade** e aumenta a segurança no processamento de documentos sensíveis: RG, CNH, notas fiscais, boletos e comprovantes.

O motor é **100% agnóstico de provedor**: a mesma pipeline roda com **Azure AI Document Intelligence** (modo real), com **OCR local** (sem chave, sem custo) ou com dados de referência (demo). O **produto online** faz OCR real direto no navegador com Tesseract.js — nada sai da máquina do usuário.

---

## ✨ O que a solução detecta

| Categoria | Regras |
|---|---|
| 🔢 **Validação estrutural** | Dígitos verificadores de **CPF** e **CNPJ** (algoritmos oficiais), formatos de RG, CNH, CEP e placa |
| 📅 **Cronologia de datas** | Nascimento no futuro, emissão anterior ao nascimento, **validade expirada**, título vencido |
| 🧾 **Consistência financeira** | Soma dos itens ≠ total da nota, valores não positivos |
| 👤 **Cruzamento com cadastro** | Nome do documento vs. nome na base (similaridade), CPF inexistente na base |
| 🖼️ **Qualidade do OCR** | Confiança média baixa ou campos críticos com leitura insegura |
| 🔏 **Integridade** | SHA-256 do arquivo para rastreio de reenvio/duplicidade |
| 📋 **Completude** | Campos obrigatórios por tipo de documento |

Cada falha soma peso por severidade (informação / aviso / crítico) e gera **score de risco 0–100** com classificação **BAIXO / MÉDIO / ALTO** e parecer **APROVADO / APROVADO COM RESSALVAS / REPROVADO**.

## 💻 Tecnologias

- **Azure AI Document Intelligence** — modelo `prebuilt-read` via REST (provedor opcional, sem SDK)
- **RapidOCR** (ONNX Runtime) — OCR local no CLI, sem instalação de sistema
- **Tesseract.js** — OCR real no navegador (produto online, 100% client-side)
- **Python 3** — CLI, motor de regras e geração de amostras sintéticas
- **JavaScript puro** — produto web (mesmas regras do CLI, espelhadas 1:1)
- **Pillow** — geração dos documentos de exemplo (100% fictícios)

## 🧪 Resultados nas amostras (documentos sintéticos)

| Documento | Score | Classificação | Parecer |
|---|---|---|---|
| `rg_ok.png` | **0** | 🟢 BAIXO | APROVADO |
| `rg_adulterado.png` *(CPF inválido + validade expirada)* | **72** | 🔴 ALTO | REPROVADO |
| `nf_ok.png` | **0** | 🟢 BAIXO | APROVADO |
| `nf_suspeita.png` *(CNPJ inválido + total ≠ soma)* | **60** | 🔴 ALTO | REPROVADO |
| `boleto_ok.png` | **0** | 🟢 BAIXO | APROVADO |
| `comprovante_inconsistente.png` *(nome ≠ cadastro)* | **30** | 🟠 MÉDIO | REPROVADO |

Os mesmos scores são produzidos pelo CLI (Python) e pelo produto web (JS) — verificado por teste automatizado.

## 🚀 Como usar

### Produto online (sem instalar nada)

Acesse **[everferreira.github.io/analise-documentos-anti-fraude-azureai/](https://everferreira.github.io/analise-documentos-anti-fraude-azureai/)**, arraste um documento (ou escolha uma amostra) e veja o relatório. O OCR roda no seu navegador.

### CLI (Python)

```bash
# 1. ambiente (venv com uv)
uv venv && uv pip install -r requirements.txt

# 2. analisa todas as amostras com OCR local real
python3 src/cli.py --todos --extractor local --cadastro scripts/cadastro.json

# 3. um documento específico, modo demo (sem OCR)
python3 src/cli.py amostras/rg_adulterado.png --tipo rg --extractor demo

# 4. saída JSON (integração)
python3 src/cli.py amostras/nf_suspeita.png --extractor local --json
```

### Ativando o modo Azure (opcional)

O provedor `azure` usa **Azure AI Document Intelligence** via REST (biblioteca padrão, sem SDK):

```bash
# 1. No portal Azure, crie um recurso "Document Intelligence" (tier F0 gratuito)
# 2. Copie o endpoint e uma chave
export AZURE_DOC_INTEL_ENDPOINT="https://SEU-RECURSO.cognitiveservices.azure.com/"
export AZURE_DOC_INTEL_KEY="SUA_CHAVE"
python3 src/cli.py documento.png --extractor azure
```

> ⚠️ Chaves nunca vão para o repositório — use variáveis de ambiente (veja `.env.example`).

## 📊 Arquitetura

```
documento → [provedor de extração] → texto + confianças
                ├─ azure  (Azure AI Document Intelligence, REST)
                ├─ local  (RapidOCR, ONNX)
                └─ demo   (extrações de referência das amostras)
     ↓
[parser de campos] → campos estruturados (CPF, CNPJ, nome, datas, valores…)
     ↓
[motor de regras] → verificações por severidade
     ↓
[score] → 0–100 · BAIXO/MÉDIO/ALTO · APROVADO/REPROVADO
```

A separação em camadas garante que **as regras são as mesmas** independente do provedor — o que vale para o Azure vale para o OCR local.

## 📂 Estrutura do projeto

```
analise-documentos-anti-fraude-azureai/
├── amostras/                 # documentos sintéticos + catálogo demo
├── scripts/
│   ├── gerar_amostras.py     # gera os docs de exemplo (CPF/CNPJ válidos de verdade)
│   └── cadastro.json         # base de cadastro para cruzamento
├── src/
│   ├── cli.py                # interface de linha de comando
│   ├── anti_fraude/          # motor: models, parser, rules, score
│   └── extractors/           # provedores: azure, local (rapidocr), demo
└── docs/                      # produto online (GitHub Pages — deploy do branch main, pasta /docs)
    ├── index.html
    ├── styles.css
    ├── app.js                # mesmo motor de regras, em JS
    └── samples/              # amostras + extrações de referência
```

## 📝 Como foi feito

1. **Motor de regras** em Python com os algoritmos oficiais de CPF/CNPJ e validações de datas/valores/consistência
2. **Gerador de amostras** com Pillow: cria RG, notas fiscais, boleto e comprovante fictícios — com CPF/CNPJ **válidos calculados pelos dígitos verificadores** e versões adulteradas
3. **Provedores de extração** plugáveis (Azure REST / RapidOCR local / demo) alimentando o mesmo parser
4. **Validação real**: CLI testado ponta a ponta com OCR real nas 6 amostras (6/6 scores corretos)
5. **Produto web**: motor portado 1:1 para JS + Tesseract.js (OCR no navegador), verificado com os textos reais de OCR (6/6)

## 👩‍💻 Autora

<p>
    <img align=left margin=10 width=80 src="https://avatars.githubusercontent.com/u/104384378?v=4" />
    <p>&nbsp&nbsp&nbsp<b>Ever Maria Tobias Ferreira</b><br>
    &nbsp&nbsp&nbsp
    <a href="https://github.com/everferreira">GitHub</a>&nbsp;|&nbsp;
    <a href="https://www.linkedin.com/in/evermaria">LinkedIn</a>&nbsp;|&nbsp;
    <a href="https://dio.me/users/contatoeverferreira">DIO</a>
    </p>
</p>

---

⌨️ com 💜 por [Ever Ferreira](https://github.com/everferreira) — Certificação IA-102 (DIO · Microsoft)