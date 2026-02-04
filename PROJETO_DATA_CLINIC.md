# Especificação Técnica: Data Clinic AI

**Versão:** 1.0
**Autor:** Joel Duarte (Portfólio)
**Stack:** Python, Streamlit, SQLite, OpenRouter API

## 1. Visão Geral do Produto
O **Data Clinic AI** é uma ferramenta de ETL "inteligente" para higienização de dados. Diferente de scripts fixos, ele usa LLMs para analisar a estrutura de um CSV "sujo", entender o contexto das colunas e gerar queries SQL automáticas para limpar os dados (padronizar datas, corrigir CPFs, remover duplicatas).

## 2. Arquitetura de IA (Model Routing)
O sistema deve utilizar a API do OpenRouter, roteando as tarefas para os modelos específicos definidos na arquitetura, visando custo zero e alta performance:

* **Análise de Estrutura (Schema Analysis):**
    * **Modelo:** `meta-llama/llama-3.3-70b-instruct:free`
    * **Função:** Recebe as primeiras 5 linhas do CSV. Retorna um JSON identificando o tipo de dado provável de cada coluna (ex: "Coluna 'nsc' parece ser uma Data de Nascimento") e dependências entre colunas.
    * *Justificativa:* Alta fidelidade de instrução para mapeamento.

* **Engenharia de Correção (SQL Gen):**
    * **Modelo:** `deepseek/deepseek-r1-0528:free`
    * **Função:** Recebe o diagnóstico do Llama e gera o código SQL (SQLite) para transformar a tabela "suja" na tabela "limpa".
    * *Justificativa:* Capacidade superior de raciocínio (Chain of Thought) para planejar lógica complexa de limpeza.

* *(Opcional/Future)* **Interface Chat:**
    * **Modelo:** `deepseek/deepseek-chat` (ou GPT-4o-mini se configurado)
    * **Função:** Explicar para o usuário o que foi limpo.

## 3. Estrutura de Pastas Sugerida
```
data-clinic-ai/
├── .env                # Chave OPENROUTER_API_KEY
├── requirements.txt    # streamlit, pandas, openai, python-dotenv, sqlalchemy
├── app.py              # Interface Principal (Frontend)
├── src/
│   ├── database.py     # Gerenciamento do SQLite (Load CSV -> Table)
│   ├── llm_client.py   # Cliente OpenRouter (Llama e Deepseek)
│   └── sanitizer.py    # Orquestrador (Coordena o fluxo IA -> SQL)
└── assets/             # Logos e exemplos de CSV
```

## 4. Plano de Implementação Passo a Passo

### Passo 1: Configuração do Ambiente e Backend Básico
* **Objetivo:** Criar o ambiente virtual e a função básica de carregar CSV para SQLite.
* **Tarefa:**
    1.  Criar `requirements.txt` com: `streamlit`, `pandas`, `openai`, `python-dotenv`.
    2.  Criar `src/database.py` com uma classe `DataManager`.
    3.  Implementar método `load_csv_to_raw(file)`: Carrega o CSV enviado pelo usuário para uma tabela temporária `raw_data` no SQLite em memória.

### Passo 2: Integração com OpenRouter (O Cérebro)
* **Objetivo:** Conectar nos modelos gratuitos escolhidos.
* **Tarefa:**
    1.  Criar `src/llm_client.py`.
    2.  Implementar função `analyze_schema(dataframe_head)`:
        * Montar prompt para o `meta-llama/llama-3.3-70b-instruct:free`.
        * Pedir saída em JSON com: `{coluna_original: sugestao_tipo}`.
    3.  Implementar função `generate_cleaning_sql(schema_json)`:
        * Montar prompt para o `deepseek/deepseek-r1-0528:free`.
        * Instrução: "Crie uma Query SQL SQLite que leia da tabela 'raw_data' e insira na tabela 'clean_data', aplicando as seguintes correções...".

### Passo 3: Interface do Usuário (Streamlit)
* **Objetivo:** O usuário vê o "antes e depois".
* **Tarefa:**
    1.  Em `app.py`, criar um uploader de arquivos.
    2.  Mostrar um `st.dataframe` com os dados originais ("Sujos").
    3.  Botão "Diagnosticar com IA" (chama o Llama).
    4.  Botão "Higienizar Dados" (chama o Deepseek + Executa SQL).
    5.  Mostrar `st.dataframe` com os dados finais ("Limpos") e botão de download CSV.

### Passo 4: Refinamento e Logs
* **Objetivo:** Mostrar que o sistema é robusto (importante para portfólio).
* **Tarefa:**
    1.  Adicionar uma aba "Logs de IA" no Streamlit para mostrar o "Raciocínio" do Deepseek (o texto que ele gera antes do SQL). Isso impressiona recrutadores.
    2.  Tratamento de erros: Se a IA gerar SQL inválido, capturar o erro e pedir para ela corrigir (Retry Logic simples).

---

## Dica para o README do GitHub
Quando finalizar, adicione esta descrição técnica no topo do seu repositório:

> **"Pipeline de ETL Autônomo utilizando Arquitetura Multi-Model (Llama 3.3 para Análise Semântica e DeepSeek R1 para Lógica de Engenharia de Dados), orquestrado via OpenRouter Free Tier."**