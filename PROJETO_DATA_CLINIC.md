# Especificação Técnica: Data Clinic AI

**Versão:** 2.0
**Autor:** Joel Duarte (Portfólio)
**Stack:** Python, Streamlit, SQLite, OpenRouter API
**Status:** MVP Completo ✅

---

## 1. Visão Geral do Produto

O **Data Clinic AI** é uma ferramenta de ETL "inteligente" para higienização de dados. Diferente de scripts fixos, ele usa LLMs para analisar a estrutura de um CSV "sujo", entender o contexto das colunas e gerar queries SQL automáticas para limpar os dados (padronizar datas, corrigir CPFs, normalizar telefones, etc.).

---

## 2. Funcionalidades Implementadas

### Core
- ✅ Upload de arquivos CSV com seleção de separador e encoding
- ✅ Análise automática de schema via LLM
- ✅ Geração de SQL de limpeza via LLM
- ✅ Execução do SQL em SQLite in-memory
- ✅ Download do CSV limpo
- ✅ Visualização dos dados antes/depois

### Sistema de Modelos
- ✅ **3 planos de modelos**: Gratuito, Pago e Personalizado
- ✅ **Fallback automático**: Se um modelo falhar por rate limit, tenta outro
- ✅ **Troca dinâmica**: Muda de plano em runtime sem reiniciar

### Configurações
- ✅ **API Key configurável pela interface** (salva localmente)
- ✅ **Max Retries configurável** (0 a 10 tentativas)
- ✅ **Arquivo config.local.json** (nunca vai pro GitHub)

### Robustez
- ✅ **Retry automático**: Se o SQL falhar, pede correção à IA
- ✅ **Logs detalhados**: Timeline de execução com timestamps
- ✅ **Mensagens de erro amigáveis**: Rate limit, spend limit, auth, timeout

### UX
- ✅ Botões de reset (topo e fim da página)
- ✅ Reset automático ao trocar de modelo
- ✅ Suporte a temas claro/escuro
- ✅ Separadores: vírgula, ponto-e-vírgula, tab, pipe
- ✅ Encodings: UTF-8, Latin-1, Windows-1252

---

## 3. Arquitetura de IA (Model Routing)

O sistema utiliza a API do OpenRouter com roteamento dinâmico de modelos:

### Plano Gratuito (default)
| Tarefa | Modelo | Fallback |
|--------|--------|----------|
| Análise de Schema | `tngtech/deepseek-r1t2-chimera:free` | `meta-llama/llama-3.3-70b-instruct:free` |
| Geração de SQL | `tngtech/deepseek-r1t2-chimera:free` | `meta-llama/llama-3.3-70b-instruct:free` |

### Plano Pago
| Tarefa | Modelo | Fallback |
|--------|--------|----------|
| Análise de Schema | `openai/gpt-4o-mini` | `deepseek/deepseek-chat-v3-0324` |
| Geração de SQL | `openai/gpt-4o-mini` | `deepseek/deepseek-chat-v3-0324` |

### Plano Personalizado
- Usuário define qualquer modelo do OpenRouter pelo ID

---

## 4. Regras de Padronização (Prompt Engineering)

O prompt de geração de SQL inclui regras explícitas:

| Tipo de Dado | Formato de Saída | Transformação |
|--------------|------------------|---------------|
| Datas | `YYYY-MM-DD` | Lógica para identificar dia/mês/ano |
| Telefones | Apenas dígitos | Remove toda formatação |
| CPF/CNPJ | Apenas dígitos (TEXT) | Remove pontuação, preserva zeros |
| Emails | Minúsculas | `LOWER(TRIM())` |
| Nomes | Maiúsculas | `UPPER(TRIM())` |
| Cidades | Maiúsculas | `UPPER(TRIM())` |

---

## 5. Estrutura de Pastas

```
data-clinic-ai/
├── app.py                  # Interface Streamlit
├── src/
│   ├── __init__.py
│   ├── config.py           # Gerenciamento de configurações locais
│   ├── database.py         # Gerenciamento SQLite in-memory
│   ├── llm_client.py       # Cliente OpenRouter + planos de modelos
│   └── sanitizer.py        # Orquestrador do pipeline + retry logic
├── assets/
│   └── exemplo_dados_sujos.csv
├── config.local.json       # Configurações do usuário (gitignore)
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── PROJETO_DATA_CLINIC.md  # Este arquivo
```

---

## 6. Limitações Conhecidas

### SQLite
O sistema usa SQLite in-memory, que não suporta:
- `REGEXP_REPLACE`, `REGEXP`
- `INITCAP`, `PROPER`
- `STRING_AGG`, CTEs complexas
- Funções de window em INSERT

O prompt instrui explicitamente a IA a usar apenas funções compatíveis.

### Rate Limits (Plano Gratuito)
- 50 requisições/dia para modelos gratuitos
- Reset à meia-noite UTC
- Adicionar $10 de créditos desbloqueia 1000 req/dia

### Formatos de Arquivo
- Atualmente apenas CSV
- Excel (.xlsx) e SQLite (.db) planejados para versões futuras

---

## 7. Próximas Versões (Roadmap)

### v2.1 - Novos Formatos
- [ ] Suporte a Excel (.xlsx, .xls)
- [ ] Suporte a SQLite (.db, .sqlite)
- [ ] Detecção automática de encoding

### v2.2 - Melhorias de UX
- [ ] Preview das transformações antes de executar
- [ ] Edição manual do SQL gerado
- [ ] Histórico de sessões

### v2.3 - Features Avançadas
- [ ] Chat para explicar o que foi limpo
- [ ] Sugestões de correção para erros comuns
- [ ] Templates de limpeza reutilizáveis

---

## 8. Como Executar

```bash
# Clone
git clone https://github.com/joellduarte/data-clinic-ai.git
cd data-clinic-ai

# Ambiente virtual
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Dependências
pip install -r requirements.txt

# Executar
streamlit run app.py
```

Configure a API Key pela interface (Sidebar → Configurações).

---

## 9. Sobre o Projeto

Este projeto faz parte do meu portfólio técnico. O objetivo foi demonstrar:

1. **Orquestração Multi-Model** - Usar o modelo certo para cada tarefa
2. **Fallback automático** - Resiliência quando um modelo falha
3. **Retry inteligente** - Correção automática de erros
4. **Configuração flexível** - Usuário escolhe seus modelos
5. **Privacidade** - Configurações salvas localmente

**Joel Duarte**
Engenheiro de Dados | Suporte N3 | Automação de Processos
