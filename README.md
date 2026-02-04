# Data Clinic AI

**Autonomous ETL Pipeline with Multi-Model LLM Orchestration**

---

## O Problema

Em anos trabalhando com sustentação de sistemas e engenharia de dados, o maior gargalo sempre foi o mesmo: receber dados "sujos" de clientes para importação.

Datas em 15 formatos diferentes. CPFs ora com máscara, ora sem. Nomes em CAPS LOCK. Telefones que são campos de texto livre. Encodings quebrados. E o clássico: "a planilha estava funcionando no meu Excel".

A solução padrão? Abrir o Python, escrever um script descartável com 47 `replace()` e `try/except`, rodar, rezar, e repetir na semana seguinte quando chegar outra planilha igualmente bagunçada.

Criei este projeto para acabar com isso. Em vez de eu analisar cada CSV e escrever regras de limpeza manualmente, deleguei essa tarefa para LLMs. Eles leem a estrutura, identificam os problemas e geram o SQL de correção. Eu só aprovo e baixo o resultado.

---

## A Solução

### Arquitetura Multi-Model

Utilizei uma abordagem Multi-Model via OpenRouter para otimizar custos e precisão. Cada modelo faz o que faz de melhor:

| Etapa | Modelo | Função |
|-------|--------|--------|
| **Análise de Schema** | Llama 3.3 70B | Lê as primeiras linhas do CSV e identifica o tipo de cada coluna (CPF, Data, Email, etc.) e os problemas encontrados. Rápido e barato para tarefas de classificação. |
| **Geração de SQL** | DeepSeek R1 | Recebe o diagnóstico e escreve queries SQL de limpeza para SQLite. Escolhi este modelo pela capacidade superior de raciocínio (Chain of Thought) — ele "pensa" antes de escrever o código. |

### Fluxo

```
CSV Upload → SQLite (in-memory)
     │
     ▼
[Llama 3.3] Analisa schema → JSON com tipos e problemas detectados
     │
     ▼
[DeepSeek R1] Gera SQL de limpeza → CREATE TABLE clean_data + INSERT
     │
     ▼
Executa SQL → Dados limpos prontos para download
```

### Retry Automático

Se o SQL gerado falhar (sintaxe inválida, coluna inexistente), o sistema captura o erro e pede para o modelo corrigir. Até 2 tentativas automáticas antes de reportar falha.

---

## Como Usar

### 1. Clone o repositório
```bash
git clone https://github.com/joellduarte/data-clinic-ai.git
cd data-clinic-ai
```

### 2. Crie o ambiente virtual
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Instale as dependências
```bash
pip install -r requirements.txt
```

### 4. Configure a API Key

Deixei um `.env.example` como template. Copie e adicione sua chave do OpenRouter:

```bash
cp .env.example .env
```

Edite o `.env`:
```
OPENROUTER_API_KEY=sk-or-v1-sua-chave-aqui
```

> Chave gratuita em: https://openrouter.ai/keys

### 5. Execute
```bash
streamlit run app.py
```

Acesse `http://localhost:8501`, faça upload de um CSV e teste.

Há um arquivo de exemplo em `assets/exemplo_dados_sujos.csv` com problemas típicos (datas inconsistentes, CPFs misturados, nomes mal formatados).

---

## Tecnologias

- **Python 3.10+**
- **Streamlit** — Interface web
- **SQLite (in-memory)** — Processamento dos dados sem persistência
- **Pandas** — Manipulação de DataFrames
- **OpenRouter API** — Orquestração de múltiplos LLMs (Llama, DeepSeek)
- **OpenAI SDK** — Cliente HTTP para a API

---

## Estrutura do Projeto

```
data-clinic-ai/
├── app.py              # Interface Streamlit
├── src/
│   ├── database.py     # Gerenciamento SQLite
│   ├── llm_client.py   # Cliente OpenRouter (Llama + DeepSeek)
│   └── sanitizer.py    # Orquestrador do pipeline + retry logic
├── assets/
│   └── exemplo_dados_sujos.csv
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Autor

**Joel Duarte**
Engenheiro de Dados | Suporte N3 | Automação de Processos

Este projeto faz parte do meu portfólio técnico. O objetivo foi demonstrar orquestração de múltiplos modelos de IA para resolver um problema real de engenharia de dados — não apenas "chamar uma API", mas arquitetar um pipeline que escolhe o modelo certo para cada tarefa.
