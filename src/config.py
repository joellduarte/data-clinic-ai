"""
Data Clinic AI - Gerenciamento de Configurações Locais
Salva configurações do usuário em arquivo local (não vai para o GitHub).
"""

import json
import os
from pathlib import Path
from typing import Optional

# Caminho do arquivo de configurações (na raiz do projeto)
CONFIG_FILE = Path(__file__).parent.parent / "config.local.json"

# Configurações padrão
DEFAULT_CONFIG = {
    "openrouter_api_key": "",
    "max_retries": 2,
}


def load_config() -> dict:
    """Carrega configurações do arquivo local."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved_config = json.load(f)
                # Mescla com defaults para garantir que novas opções existam
                config = DEFAULT_CONFIG.copy()
                config.update(saved_config)
                return config
        except (json.JSONDecodeError, IOError):
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> bool:
    """Salva configurações no arquivo local."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except IOError:
        return False


def get_api_key() -> str:
    """
    Retorna a API key do OpenRouter.
    Prioridade: 1) config.local.json, 2) variável de ambiente, 3) .env
    """
    config = load_config()
    api_key = config.get("openrouter_api_key", "")

    # Se não tem no config local, tenta variável de ambiente
    if not api_key:
        api_key = os.getenv("OPENROUTER_API_KEY", "")

    return api_key


def set_api_key(api_key: str) -> bool:
    """Define a API key e salva no arquivo local."""
    config = load_config()
    config["openrouter_api_key"] = api_key
    return save_config(config)


def get_max_retries() -> int:
    """Retorna o número máximo de retries."""
    config = load_config()
    return config.get("max_retries", DEFAULT_CONFIG["max_retries"])


def set_max_retries(max_retries: int) -> bool:
    """Define o número máximo de retries e salva."""
    config = load_config()
    config["max_retries"] = max(0, min(max_retries, 10))  # Entre 0 e 10
    return save_config(config)


def config_file_exists() -> bool:
    """Verifica se o arquivo de configuração existe."""
    return CONFIG_FILE.exists()


def get_config_path() -> str:
    """Retorna o caminho do arquivo de configuração."""
    return str(CONFIG_FILE)
