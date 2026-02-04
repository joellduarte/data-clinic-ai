# Data Clinic AI

**Pipeline de ETL Inteligente com Orquestração Multi-Model de LLMs**

---

## O Problema

Em anos trabalhando com sustentação de sistemas e engenharia de dados, o maior gargalo sempre foi o mesmo: receber dados "sujos" de clientes para importação.

Datas em 15 formatos diferentes. CPFs ora com máscara, ora sem. Nomes em CAPS LOCK. Telefones que são campos de texto livre. Encodings quebrados. E o clássico: "a planilha estava funcionando no meu Excel".

A solução padrão? Abrir o Python, escrever um script descartável com 47 `replace()` e `try/except`, rodar, rezar, e repetir na semana seguinte quando chegar outra planilha igualmente bagunçada.

Criei este projeto para acabar com isso. Em vez de eu analisar cada CSV e escrever regras de limpeza manualmente, deleguei essa tarefa para LLMs. Eles leem a estrutura, identificam os problemas e geram o SQL de correção. Eu só aprovo e baixo o resultado.

---

## A Solução

### Arquitetura Multi-Model

O sistema usa uma abordagem Multi-Model via OpenRouter. Você escolhe o plano e os modelos fazem o trabalho:

| Plano | Modelos | Uso |
|-------|---------|-----|
| **Gratuito** | DeepSeek R1T2 Chimera | Análise + SQL. Zero custo, rate limit compartilhado. |
| **Pago** | GPT-4o-mini | Análise + SQL. Mais rápido, sem rate limit. |
| **Personalizado** | Qualquer modelo do OpenRouter | Você escolhe. Cole o ID e teste. |

### Fluxo

```
CSV Upload → SQLite (in-memory)
     │
     ▼
[Modelo de Análise] Identifica tipos e problemas → JSON
     │
     ▼
[Modelo de SQL] Gera queries de limpeza → CREATE TABLE + INSERT
     │
     ▼
Executa SQL → Dados limpos prontos para download
```

### Funcionalidades

- **Retry Automático**: Se o SQL gerado falhar, o sistema pede correção automática (configurável de 0 a 10 tentativas)
- **Fallback entre modelos**: Se um modelo der rate limit, tenta outro automaticamente
- **Regras de padronização**: Datas para YYYY-MM-DD, telefones só dígitos, CPFs sem máscara, nomes em maiúsculas
- **Configurações pela interface**: API Key e preferências salvas localmente
- **Suporte a encodings**: UTF-8, Latin-1, Windows-1252
- **Separadores flexíveis**: Vírgula, ponto-e-vírgula, tab, pipe

---

## Configurações Locais (Privacidade)

**Importante**: Suas configurações ficam no seu computador. Nada é enviado para nenhum servidor além da API do OpenRouter.

O arquivo `config.local.json` é criado automaticamente quando você configura a API Key pela interface. Esse arquivo:

- Está no `.gitignore` — **nunca vai para o GitHub**
- Contém apenas suas preferências locais (API Key, max retries)
- Fica na raiz do projeto, visível para você

Você pode configurar tudo pela interface (sidebar → Configurações) ou editar o arquivo diretamente se preferir.

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

### 4. Execute
```bash
streamlit run app.py
```

Acesse `http://localhost:8501`.

### 5. Configure a API Key

Na sidebar, vá em **Configurações** e cole sua API Key do OpenRouter.

> Não tem uma? Crie grátis em: https://openrouter.ai/keys

A chave é salva localmente no `config.local.json` e nunca é enviada para lugar nenhum além do OpenRouter.

**Alternativa**: Se preferir usar variável de ambiente, crie um arquivo `.env`:
```
OPENROUTER_API_KEY=sk-or-v1-sua-chave-aqui
```

### 6. Teste

Há um arquivo de exemplo em `assets/exemplo_dados_sujos.csv` com problemas típicos (datas inconsistentes, CPFs misturados, nomes mal formatados).

---

## Tecnologias

- **Python 3.10+**
- **Streamlit** — Interface web
- **SQLite (in-memory)** — Processamento dos dados sem persistência
- **Pandas** — Manipulação de DataFrames
- **OpenRouter API** — Orquestração de múltiplos LLMs
- **OpenAI SDK** — Cliente HTTP para a API

---

## Estrutura do Projeto

```
data-clinic-ai/
├── app.py                  # Interface Streamlit
├── src/
│   ├── config.py           # Gerenciamento de configurações locais
│   ├── database.py         # Gerenciamento SQLite
│   ├── llm_client.py       # Cliente OpenRouter + planos de modelos
│   └── sanitizer.py        # Orquestrador do pipeline + retry logic
├── assets/
│   └── exemplo_dados_sujos.csv
├── config.local.json       # Suas configurações (criado automaticamente, NÃO vai pro git)
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Autor

**Joel Duarte**
Engenheiro de Dados | Suporte N3 | Automação de Processos

Este projeto faz parte do meu portfólio técnico. O objetivo foi demonstrar orquestração de múltiplos modelos de IA para resolver um problema real de engenharia de dados — não apenas "chamar uma API", mas arquitetar um pipeline que escolhe o modelo certo para cada tarefa, com fallback automático, retry inteligente e configuração flexível.

---

## Licença

MIT — use como quiser.
