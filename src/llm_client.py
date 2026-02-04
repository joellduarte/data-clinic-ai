"""
Data Clinic AI - Cliente OpenRouter para LLMs
Integração com Llama 3.3 (análise) e DeepSeek R1 (geração SQL).
"""

import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

# Configuração dos modelos
MODELS = {
    "analysis": "meta-llama/llama-3.3-70b-instruct:free",
    "sql_gen": "deepseek/deepseek-r1-0528:free",
    "chat": "deepseek/deepseek-chat",
}

# Cliente OpenRouter (compatível com OpenAI SDK)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)


def analyze_schema(dataframe_head: str, column_names: list[str]) -> dict:
    """
    Analisa a estrutura do CSV usando Llama 3.3 70B.

    Args:
        dataframe_head: String com as primeiras linhas do DataFrame (df.head().to_string())
        column_names: Lista com nomes das colunas

    Returns:
        Dict com análise de cada coluna: {coluna: {tipo, problemas, sugestao}}
    """
    prompt = f"""Você é um especialista em análise e limpeza de dados. Analise a amostra de dados abaixo e identifique:

1. O tipo de dado provável de cada coluna (ex: CPF, Data, Nome, Email, Telefone, Valor Monetário, etc.)
2. Problemas de qualidade encontrados (ex: formatos inconsistentes, valores ausentes, duplicatas prováveis)
3. Sugestões de padronização para cada coluna

COLUNAS: {column_names}

AMOSTRA DOS DADOS:
{dataframe_head}

Responda APENAS com um JSON válido no seguinte formato (sem markdown, sem explicações):
{{
    "nome_coluna": {{
        "tipo_identificado": "tipo do dado",
        "problemas": ["lista de problemas encontrados"],
        "sugestao_limpeza": "como padronizar/limpar"
    }}
}}
"""

    response = client.chat.completions.create(
        model=MODELS["analysis"],
        messages=[
            {
                "role": "system",
                "content": "Você é um analista de dados expert. Responda apenas em JSON válido, sem markdown."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=2000,
    )

    response_text = response.choices[0].message.content.strip()

    # Tenta extrair JSON da resposta
    schema_analysis = _extract_json(response_text)

    return {
        "analysis": schema_analysis,
        "raw_response": response_text,
        "model": MODELS["analysis"],
    }


def generate_cleaning_sql(schema_analysis: dict, column_names: list[str], sample_data: str) -> dict:
    """
    Gera queries SQL de limpeza usando DeepSeek R1.

    Args:
        schema_analysis: Resultado da análise do schema (do analyze_schema)
        column_names: Lista com nomes das colunas
        sample_data: Amostra dos dados para contexto

    Returns:
        Dict com SQL gerado e raciocínio do modelo
    """
    analysis_json = json.dumps(schema_analysis.get("analysis", {}), ensure_ascii=False, indent=2)

    prompt = f"""Você é um engenheiro de dados especialista em SQL. Com base na análise abaixo, crie queries SQL para o SQLite que:

1. Leiam da tabela 'raw_data' (já existente)
2. Apliquem as transformações de limpeza necessárias
3. Insiram os dados limpos em uma nova tabela 'clean_data'

ANÁLISE DAS COLUNAS:
{analysis_json}

COLUNAS ORIGINAIS: {column_names}

AMOSTRA DOS DADOS:
{sample_data}

REGRAS IMPORTANTES:
- Use sintaxe SQLite válida
- Crie a tabela 'clean_data' antes de inserir (CREATE TABLE IF NOT EXISTS)
- Padronize datas para formato ISO (YYYY-MM-DD)
- Remova espaços extras com TRIM()
- CPFs devem ter apenas números (11 dígitos)
- Telefones devem ter apenas números
- Use COALESCE para tratar NULLs quando apropriado
- Converta texto para maiúsculas/minúsculas conforme adequado

Responda com:
1. Primeiro, seu raciocínio sobre as transformações (em português)
2. Depois, o código SQL completo entre ```sql e ```

Seja detalhado no raciocínio para mostrar seu processo de pensamento.
"""

    response = client.chat.completions.create(
        model=MODELS["sql_gen"],
        messages=[
            {
                "role": "system",
                "content": "Você é um engenheiro de dados sênior. Explique seu raciocínio antes de gerar o SQL."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=4000,
    )

    response_text = response.choices[0].message.content.strip()

    # Extrai SQL e raciocínio
    sql_code = _extract_sql(response_text)
    reasoning = _extract_reasoning(response_text)

    return {
        "sql": sql_code,
        "reasoning": reasoning,
        "raw_response": response_text,
        "model": MODELS["sql_gen"],
    }


def _extract_json(text: str) -> dict:
    """Extrai JSON de uma resposta que pode conter texto adicional."""
    # Remove blocos de código markdown se presentes
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)

    # Tenta encontrar o JSON na resposta
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Tenta encontrar JSON entre chaves
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

    return {"error": "Não foi possível extrair JSON", "raw": text}


def _extract_sql(text: str) -> str:
    """Extrai código SQL de uma resposta."""
    # Procura por blocos ```sql ... ```
    match = re.search(r'```sql\s*([\s\S]*?)```', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Procura por blocos ``` ... ``` genéricos
    match = re.search(r'```\s*([\s\S]*?)```', text)
    if match:
        return match.group(1).strip()

    # Se não encontrar blocos, procura por statements SQL
    sql_keywords = r'(CREATE|INSERT|SELECT|UPDATE|DELETE|ALTER|DROP)'
    match = re.search(f'{sql_keywords}[\\s\\S]*?;', text, re.IGNORECASE)
    if match:
        # Pega todo o SQL até o final
        start = match.start()
        return text[start:].strip()

    return text


def _extract_reasoning(text: str) -> str:
    """Extrai o raciocínio (texto antes do SQL) da resposta."""
    # Remove blocos de código SQL
    reasoning = re.sub(r'```sql[\s\S]*?```', '', text, flags=re.IGNORECASE)
    reasoning = re.sub(r'```[\s\S]*?```', '', reasoning)

    # Limpa e retorna
    reasoning = reasoning.strip()

    # Se sobrou muito pouco, retorna a resposta original sem SQL
    if len(reasoning) < 50:
        # Pega tudo antes do primeiro bloco de código
        match = re.search(r'^([\s\S]*?)```', text)
        if match:
            return match.group(1).strip()

    return reasoning


def fix_sql_error(original_sql: str, error_message: str, column_names: list[str]) -> dict:
    """
    Pede para a IA corrigir um SQL que falhou.

    Args:
        original_sql: SQL que gerou erro
        error_message: Mensagem de erro do SQLite
        column_names: Colunas da tabela original

    Returns:
        Dict com SQL corrigido e raciocínio
    """
    prompt = f"""O SQL abaixo gerou um erro ao ser executado no SQLite. Corrija o problema.

SQL ORIGINAL:
```sql
{original_sql}
```

ERRO RETORNADO:
{error_message}

COLUNAS DISPONÍVEIS NA TABELA 'raw_data': {column_names}

INSTRUÇÕES:
1. Analise o erro e identifique a causa
2. Corrija o SQL mantendo a mesma lógica de limpeza
3. Certifique-se de que a sintaxe é válida para SQLite

Responda com:
1. Breve explicação do problema encontrado
2. SQL corrigido entre ```sql e ```
"""

    response = client.chat.completions.create(
        model=MODELS["sql_gen"],
        messages=[
            {
                "role": "system",
                "content": "Você é um especialista em depuração de SQL. Seja direto e corrija o erro."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=3000,
    )

    response_text = response.choices[0].message.content.strip()
    sql_code = _extract_sql(response_text)
    reasoning = _extract_reasoning(response_text)

    return {
        "sql": sql_code,
        "reasoning": reasoning,
        "raw_response": response_text,
        "model": MODELS["sql_gen"],
        "is_retry": True,
    }


def test_connection() -> bool:
    """Testa se a conexão com OpenRouter está funcionando."""
    try:
        response = client.chat.completions.create(
            model=MODELS["analysis"],
            messages=[{"role": "user", "content": "Responda apenas: OK"}],
            max_tokens=10,
        )
        return "ok" in response.choices[0].message.content.lower()
    except Exception as e:
        print(f"Erro de conexão: {e}")
        return False
