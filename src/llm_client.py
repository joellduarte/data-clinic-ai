"""
Data Clinic AI - Cliente OpenRouter para LLMs
Suporta modelos gratuitos e pagos com troca dinâmica e fallback automático.
"""

import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv
from typing import Optional

from .config import get_api_key

load_dotenv()

# Configuração dos planos de modelos
MODEL_PLANS = {
    "free": {
        "name": "Gratuito",
        "analysis": "tngtech/deepseek-r1t2-chimera:free",
        "analysis_fallback": "meta-llama/llama-3.3-70b-instruct:free",
        "sql_gen": "tngtech/deepseek-r1t2-chimera:free",
        "sql_gen_fallback": "meta-llama/llama-3.3-70b-instruct:free",
        "pricing": {
            "analysis": {"input": 0, "output": 0},
            "sql_gen": {"input": 0, "output": 0},
        },
        "description": "Modelos gratuitos com fallback automático",
    },
    "paid": {
        "name": "Pago",
        "analysis": "openai/gpt-4o-mini",
        "analysis_fallback": "deepseek/deepseek-chat-v3-0324",
        "sql_gen": "openai/gpt-4o-mini",
        "sql_gen_fallback": "deepseek/deepseek-chat-v3-0324",
        "pricing": {
            "analysis": {"input": 0.15, "output": 0.60},
            "sql_gen": {"input": 0.15, "output": 0.60},
        },
        "description": "Modelos pagos, mais rápidos e sem rate limit",
    },
    "custom": {
        "name": "Personalizado",
        "analysis": "",  # Será preenchido pelo usuário
        "analysis_fallback": None,
        "sql_gen": "",  # Será preenchido pelo usuário
        "sql_gen_fallback": None,
        "pricing": {
            "analysis": {"input": 0, "output": 0},
            "sql_gen": {"input": 0, "output": 0},
        },
        "description": "Modelos personalizados definidos pelo usuário",
    },
}

# Modelos personalizados (alterados via set_custom_models)
_custom_models = {
    "analysis": "",
    "sql_gen": "",
}

# Plano atual (pode ser alterado em runtime)
_current_plan = "free"


def get_current_plan() -> str:
    """Retorna o plano atual."""
    return _current_plan


def set_plan(plan: str) -> bool:
    """Define o plano de modelos a usar."""
    global _current_plan
    if plan in MODEL_PLANS:
        _current_plan = plan
        return True
    return False


def get_plan_info(plan: str = None) -> dict:
    """Retorna informações sobre um plano."""
    if plan is None:
        plan = _current_plan
    return MODEL_PLANS.get(plan, MODEL_PLANS["free"])


def get_current_models() -> dict:
    """Retorna os modelos do plano atual."""
    if _current_plan == "custom":
        return {
            "analysis": _custom_models["analysis"],
            "sql_gen": _custom_models["sql_gen"],
        }
    plan_info = MODEL_PLANS[_current_plan]
    return {
        "analysis": plan_info["analysis"],
        "sql_gen": plan_info["sql_gen"],
    }


def set_custom_models(analysis_model: str, sql_model: str):
    """Define os modelos personalizados."""
    global _custom_models
    _custom_models["analysis"] = analysis_model
    _custom_models["sql_gen"] = sql_model


def get_custom_models() -> dict:
    """Retorna os modelos personalizados atuais."""
    return _custom_models.copy()


# Cliente OpenRouter (inicializado com a API key das configurações)
def _create_client():
    """Cria o cliente OpenRouter com a API key atual."""
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=get_api_key(),
    )


client = _create_client()


def refresh_client():
    """Recria o cliente com a API key atualizada."""
    global client
    client = _create_client()


def _is_rate_or_limit_error(error: Exception) -> bool:
    """Verifica se é erro de rate limit ou spend limit."""
    error_str = str(error).lower()
    return any(x in error_str for x in ["429", "402", "rate", "limit", "exceeded"])


def _call_llm_with_fallback(
    model_key: str,
    messages: list,
    temperature: float = 0.1,
    max_tokens: int = 2000
) -> tuple[str, str]:
    """
    Chama o LLM com fallback automático se o modelo principal falhar.

    Args:
        model_key: "analysis" ou "sql_gen"
        messages: Lista de mensagens para o chat
        temperature: Temperatura do modelo
        max_tokens: Máximo de tokens na resposta

    Returns:
        Tupla (response_text, model_used)
    """
    # Para plano personalizado, usa os modelos definidos pelo usuário
    if _current_plan == "custom":
        primary_model = _custom_models[model_key]
        fallback_model = None
    else:
        plan_info = MODEL_PLANS[_current_plan]
        primary_model = plan_info[model_key]
        fallback_model = plan_info.get(f"{model_key}_fallback")

    # Tenta o modelo principal
    try:
        response = client.chat.completions.create(
            model=primary_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip(), primary_model

    except Exception as e:
        # Se for erro de rate/limit e temos fallback, tenta o fallback
        if _is_rate_or_limit_error(e) and fallback_model:
            try:
                response = client.chat.completions.create(
                    model=fallback_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content.strip(), fallback_model
            except Exception as e2:
                # Se fallback também falhar, relança o erro
                raise Exception(f"Modelo principal ({primary_model}) e fallback ({fallback_model}) falharam. Erro: {str(e2)}")
        else:
            raise


def analyze_schema(dataframe_head: str, column_names: list[str]) -> dict:
    """
    Analisa a estrutura do CSV.
    Usa fallback automático se o modelo principal falhar.
    """
    prompt = f"""Você é um especialista em análise e limpeza de dados. Analise a amostra de dados abaixo.

COLUNAS: {column_names}

AMOSTRA DOS DADOS:
{dataframe_head}

Para CADA coluna, identifique:

1. **tipo_identificado**: O tipo de dado (Data, Telefone, CPF, CNPJ, Email, Nome, Cidade, Estado, CEP, Valor Monetário, Percentual, Código/ID, Texto Livre, etc.)

2. **formatos_encontrados**: Liste TODOS os formatos diferentes encontrados na amostra.
   - Para DATAS: liste cada formato (ex: ["DD/MM/YYYY", "DD-MM-YY", "YYYY-MM-DD", "D/M/YYYY", "15/Jan/2020"])
   - Para TELEFONES: liste variações (ex: ["(11) 99999-9999", "+55 11 99999-9999", "11999999999", "99999-9999"])
   - Para outros: liste as variações encontradas

3. **problemas**: Problemas de qualidade (formatos inconsistentes, valores ausentes, erros de digitação, letras onde deveria ter números, etc.)

4. **sugestao_limpeza**: Como padronizar considerando TODOS os formatos encontrados

Responda APENAS com JSON válido (sem markdown, sem explicações):
{{
    "nome_coluna": {{
        "tipo_identificado": "tipo",
        "formatos_encontrados": ["formato1", "formato2"],
        "problemas": ["problema1", "problema2"],
        "sugestao_limpeza": "descrição da limpeza"
    }}
}}
"""

    messages = [
        {
            "role": "system",
            "content": "Você é um analista de dados expert. Responda apenas em JSON válido, sem markdown."
        },
        {"role": "user", "content": prompt}
    ]

    response_text, model_used = _call_llm_with_fallback(
        "analysis", messages, temperature=0.1, max_tokens=16000
    )

    schema_analysis = _extract_json(response_text)

    return {
        "analysis": schema_analysis,
        "raw_response": response_text,
        "model": model_used,
        "plan": _current_plan,
    }


def generate_cleaning_sql(schema_analysis: dict, column_names: list[str], sample_data: str) -> dict:
    """
    Gera queries SQL de limpeza.
    Usa fallback automático se o modelo principal falhar.
    """
    analysis_json = json.dumps(schema_analysis.get("analysis", {}), ensure_ascii=False, indent=2)

    prompt = f"""Você é um engenheiro de dados especialista em SQL e padronização de dados.

TAREFA:
1. Ler da tabela 'raw_data' (já existe)
2. Limpar e PADRONIZAR os dados
3. Inserir na tabela 'clean_data'

ANÁLISE DAS COLUNAS (use os "formatos_encontrados" para criar CASE WHEN específicos!):
{analysis_json}

⚠️ IMPORTANTE: A análise acima lista os FORMATOS ENCONTRADOS em cada coluna.
Use essa informação para criar CASE WHEN que trate CADA formato diferente.
NÃO assuma um único formato - a mesma coluna pode ter múltiplos formatos!

COLUNAS: {column_names}

AMOSTRA:
{sample_data}

═══════════════════════════════════════════════════════════════
REGRAS DE PADRONIZAÇÃO INTELIGENTE
═══════════════════════════════════════════════════════════════

⚠️ REGRA PRINCIPAL: NUNCA RETORNE NULL SEM TENTAR
   - Use COALESCE para manter o valor original se não conseguir limpar
   - Exemplo: COALESCE(valor_limpo, valor_original)

📅 DATAS - Formato de saída: YYYY-MM-DD
   IMPORTANTE: Analise TODOS os padrões na amostra e crie CASE WHEN para cada um!

   Padrões comuns a detectar:
   - DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY (BR/EU)
   - MM/DD/YYYY (US)
   - YYYY-MM-DD, YYYY/MM/DD (ISO)
   - DD/MM/YY, DD-MM-YY (ano curto: >= 50 é 1900, < 50 é 2000)
   - D/M/YYYY (sem zero à esquerda)
   - Mês escrito: 15/Jan/2020, 15-Janeiro-2020, Jan 15 2020

   Conversão de mês escrito para número:
   CASE
     WHEN UPPER(mes) IN ('JAN', 'JANEIRO', 'JANUARY') THEN '01'
     WHEN UPPER(mes) IN ('FEV', 'FEVEREIRO', 'FEBRUARY', 'FEB') THEN '02'
     ... (todos os meses)
   END

   Lógica para identificar dia/mês/ano:
   - 4 dígitos consecutivos = ANO
   - Número > 31 = ANO (ex: 90, 2020)
   - Número > 12 e <= 31 = DIA (não pode ser mês)
   - Número <= 12 = pode ser DIA ou MÊS (analise posição e contexto)

   Use CASE WHEN com LENGTH e INSTR para detectar o formato de cada célula!
   Se não conseguir converter, mantenha o valor original com COALESCE.

📞 TELEFONES - Formato de saída: apenas dígitos, padronizado
   IMPORTANTE: Analise os padrões na amostra!

   Passo 1: Remover toda formatação
   REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(tel, ' ', ''), '-', ''), '(', ''), ')', ''), '+', ''), '.', '')

   Passo 2: Analisar o que sobrou (apenas dígitos)
   - 13 dígitos: código país (55) + DDD (11) + número (9 dígitos) = completo
   - 12 dígitos: código país (55) + DDD (11) + número (8 dígitos) = completo
   - 11 dígitos: DDD (11) + número (9 dígitos) = sem código país
   - 10 dígitos: DDD (11) + número (8 dígitos) = sem código país
   - 9 dígitos: número celular sem DDD
   - 8 dígitos: número fixo sem DDD

   Códigos de país comuns: 55 (Brasil), 1 (EUA/Canadá), 351 (Portugal), 54 (Argentina)
   DDDs Brasil: 11-99 (2 dígitos, começam com 1-9)

   NUNCA retorne NULL - mantenha os dígitos extraídos mesmo se incompleto.

📋 DOCUMENTOS (CPF, CNPJ, RG, etc.) - apenas dígitos como TEXT
   - Remova: . - / espaços
   - CPF: 11 dígitos
   - CNPJ: 14 dígitos
   - Mantenha zeros à esquerda (TEXT, não INTEGER)

📧 EMAILS - minúsculas, sem espaços
   LOWER(TRIM(email))

👤 NOMES - MAIÚSCULAS, sem espaços extras
   UPPER(TRIM(nome))

💰 VALORES MONETÁRIOS - apenas números e ponto decimal
   - Remova: R$, $, €, espaços, pontos de milhar
   - Converta vírgula decimal para ponto: REPLACE(valor, ',', '.')
   - Exemplo: "R$ 1.234,56" → "1234.56"

📊 OUTROS TIPOS DE DADOS
   - Analise o contexto da coluna na amostra
   - Aplique limpeza básica: TRIM, remover espaços duplicados
   - Padronize maiúsculas/minúsculas conforme o contexto

═══════════════════════════════════════════════════════════════
LIMITAÇÕES DO SQLITE
═══════════════════════════════════════════════════════════════

✅ USE APENAS:
- UPPER(), LOWER(), TRIM()
- SUBSTR(texto, inicio, tamanho)
- LENGTH(), INSTR()
- REPLACE(texto, antigo, novo) - aninhado para múltiplas substituições
- COALESCE(valor, padrao)
- CASE WHEN ... THEN ... ELSE ... END
- || para concatenar strings
- CAST(valor AS tipo)

❌ NÃO USE:
- REGEXP_REPLACE, REGEXP, LIKE com regex
- INITCAP, PROPER, CONCAT()
- STRING_AGG, GROUP_CONCAT em subqueries
- CTEs (WITH), subqueries complexas
- json_each, json_extract
- Funções de window

═══════════════════════════════════════════════════════════════
EXEMPLO DE SQL COM MÚLTIPLOS FORMATOS
═══════════════════════════════════════════════════════════════

```sql
CREATE TABLE IF NOT EXISTS clean_data (
    data_nascimento TEXT,
    telefone TEXT
);

INSERT INTO clean_data (data_nascimento, telefone)
SELECT
    -- Data: trata múltiplos formatos com CASE WHEN
    COALESCE(
        CASE
            -- Formato YYYY-MM-DD (já está correto)
            WHEN LENGTH(data) = 10 AND SUBSTR(data,5,1) = '-' AND SUBSTR(data,8,1) = '-'
            THEN data
            -- Formato DD/MM/YYYY
            WHEN LENGTH(data) = 10 AND SUBSTR(data,3,1) = '/'
            THEN SUBSTR(data,7,4) || '-' || SUBSTR(data,4,2) || '-' || SUBSTR(data,1,2)
            -- Formato DD-MM-YYYY
            WHEN LENGTH(data) = 10 AND SUBSTR(data,3,1) = '-' AND LENGTH(SUBSTR(data,7,4)) = 4
            THEN SUBSTR(data,7,4) || '-' || SUBSTR(data,4,2) || '-' || SUBSTR(data,1,2)
            -- Formato DD/MM/YY (ano curto)
            WHEN LENGTH(data) = 8 AND SUBSTR(data,3,1) = '/'
            THEN CASE WHEN CAST(SUBSTR(data,7,2) AS INTEGER) >= 50 THEN '19' ELSE '20' END || SUBSTR(data,7,2) || '-' || SUBSTR(data,4,2) || '-' || SUBSTR(data,1,2)
            ELSE NULL
        END,
        data  -- Mantém original se não conseguir converter
    ) AS data_nascimento,

    -- Telefone: remove formatação e mantém dígitos
    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(telefone, ' ', ''), '-', ''), '(', ''), ')', ''), '+', ''), '.', '') AS telefone
FROM raw_data;
```

═══════════════════════════════════════════════════════════════
REGRAS FINAIS
═══════════════════════════════════════════════════════════════

- Todas as colunas devem ser TEXT (preserva zeros à esquerda)
- Use COALESCE para NUNCA perder dados - mantenha original se não converter
- Crie CASE WHEN para CADA formato encontrado na análise
- NÃO remova duplicatas

Responda com:
1. Lista dos formatos detectados em cada coluna problemática
2. SQL entre ```sql e ```
"""

    messages = [
        {
            "role": "system",
            "content": "Você é um engenheiro de dados sênior. Explique seu raciocínio antes de gerar o SQL."
        },
        {"role": "user", "content": prompt}
    ]

    response_text, model_used = _call_llm_with_fallback(
        "sql_gen", messages, temperature=0.2, max_tokens=16000
    )

    sql_code = _extract_sql(response_text)
    reasoning = _extract_reasoning(response_text)

    return {
        "sql": sql_code,
        "reasoning": reasoning,
        "raw_response": response_text,
        "model": model_used,
        "plan": _current_plan,
    }


def fix_sql_error(original_sql: str, error_message: str, column_names: list[str]) -> dict:
    """
    Pede para a IA corrigir um SQL que falhou.
    Usa fallback automático se o modelo principal falhar.
    """
    prompt = f"""O SQL abaixo falhou no SQLite. Simplifique e corrija.

ERRO: {error_message}

SQL QUE FALHOU:
```sql
{original_sql}
```

COLUNAS DISPONÍVEIS: {column_names}

❌ SQLite NÃO TEM:
- REGEXP_REPLACE, REGEXP
- INITCAP, PROPER, CONCAT()
- STRING_AGG, CTEs (WITH)
- json_each, json_extract

✅ USE APENAS:
- UPPER(), LOWER(), TRIM()
- SUBSTR(texto, inicio, tamanho), LENGTH(), INSTR()
- REPLACE() aninhado: REPLACE(REPLACE(x, '.', ''), '-', '')
- CASE WHEN ... THEN ... ELSE ... END
- COALESCE(), || para concatenar

📋 FORMATOS DE SAÍDA:
- Datas: YYYY-MM-DD (use SUBSTR e || para reorganizar)
- Telefones: apenas dígitos (REPLACE para remover formatação)
- Documentos: apenas dígitos como TEXT
- Nomes/Cidades: UPPER(TRIM())
- Emails: LOWER(TRIM())

Responda com:
1. Uma linha explicando o problema
2. SQL corrigido entre ```sql e ```
"""

    messages = [
        {
            "role": "system",
            "content": "Você é um especialista em depuração de SQL. Seja direto e corrija o erro."
        },
        {"role": "user", "content": prompt}
    ]

    response_text, model_used = _call_llm_with_fallback(
        "sql_gen", messages, temperature=0.1, max_tokens=3000
    )

    sql_code = _extract_sql(response_text)
    reasoning = _extract_reasoning(response_text)

    return {
        "sql": sql_code,
        "reasoning": reasoning,
        "raw_response": response_text,
        "model": model_used,
        "plan": _current_plan,
        "is_retry": True,
    }


def _extract_json(text: str) -> dict:
    """Extrai JSON de uma resposta que pode conter texto adicional."""
    if not text or not text.strip():
        return {"_parse_error": True, "error": "Resposta vazia do modelo", "raw": ""}

    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)

    # Tenta parsear diretamente
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Tenta encontrar JSON entre chaves
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            # JSON pode estar truncado, tenta reparar
            json_text = match.group()
            repaired = _try_repair_json(json_text)
            if repaired:
                return repaired

    return {"_parse_error": True, "error": "Não foi possível extrair JSON", "raw": text}


def _try_repair_json(text: str) -> dict:
    """Tenta reparar um JSON truncado ou malformado."""
    # Remove trailing commas
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)

    # Conta chaves e colchetes abertos
    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')

    # Tenta fechar estruturas abertas
    if open_braces > 0 or open_brackets > 0:
        # Remove a última propriedade incompleta (se houver)
        # Procura por padrões como: "key": "value ou "key": [
        text = re.sub(r',\s*"[^"]*":\s*("[^"]*)?$', '', text)
        text = re.sub(r',\s*"[^"]*":\s*\[[^\]]*$', '', text)
        text = re.sub(r',\s*"[^"]*":\s*\{[^}]*$', '', text)

        # Fecha estruturas
        text = text.rstrip()
        if text.endswith(','):
            text = text[:-1]

        text += '}' * open_braces
        text += ']' * open_brackets

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _extract_sql(text: str) -> str:
    """Extrai código SQL de uma resposta."""
    match = re.search(r'```sql\s*([\s\S]*?)```', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    match = re.search(r'```\s*([\s\S]*?)```', text)
    if match:
        return match.group(1).strip()

    sql_keywords = r'(CREATE|INSERT|SELECT|UPDATE|DELETE|ALTER|DROP)'
    match = re.search(f'{sql_keywords}[\\s\\S]*?;', text, re.IGNORECASE)
    if match:
        start = match.start()
        return text[start:].strip()

    return text


def _extract_reasoning(text: str) -> str:
    """Extrai o raciocínio (texto antes do SQL) da resposta."""
    reasoning = re.sub(r'```sql[\s\S]*?```', '', text, flags=re.IGNORECASE)
    reasoning = re.sub(r'```[\s\S]*?```', '', reasoning)
    reasoning = reasoning.strip()

    if len(reasoning) < 50:
        match = re.search(r'^([\s\S]*?)```', text)
        if match:
            return match.group(1).strip()

    return reasoning


def test_connection() -> bool:
    """Testa se a conexão com OpenRouter está funcionando."""
    try:
        models = get_current_models()
        response = client.chat.completions.create(
            model=models["analysis"],
            messages=[{"role": "user", "content": "Responda apenas: OK"}],
            max_tokens=10,
        )
        return "ok" in response.choices[0].message.content.lower()
    except Exception as e:
        print(f"Erro de conexão: {e}")
        return False
