"""
Data Clinic AI - Gerenciamento de Banco de Dados SQLite
Responsável por carregar CSVs para tabelas temporárias em memória.
"""

import sqlite3
import pandas as pd
from typing import Optional
import io


class DataManager:
    """
    Gerencia operações de banco de dados SQLite em memória.
    Carrega CSVs para tabelas temporárias e executa queries de limpeza.
    """

    def __init__(self):
        """Inicializa conexão SQLite em memória."""
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.cursor = self.conn.cursor()

    def load_csv_to_raw(self, file) -> pd.DataFrame:
        """
        Carrega um arquivo CSV para a tabela 'raw_data' no SQLite.

        Args:
            file: Arquivo CSV (pode ser path, file-like object ou UploadedFile do Streamlit)

        Returns:
            DataFrame com os dados carregados

        Raises:
            ValueError: Se o arquivo estiver vazio ou inválido
        """
        # Lê o CSV para DataFrame
        if hasattr(file, 'read'):
            # File-like object (ex: UploadedFile do Streamlit)
            content = file.read()
            if isinstance(content, bytes):
                content = content.decode('utf-8')
            df = pd.read_csv(io.StringIO(content))
        else:
            # Path de arquivo
            df = pd.read_csv(file)

        if df.empty:
            raise ValueError("O arquivo CSV está vazio")

        # Remove tabela anterior se existir
        self.cursor.execute("DROP TABLE IF EXISTS raw_data")
        self.cursor.execute("DROP TABLE IF EXISTS clean_data")

        # Carrega DataFrame para SQLite
        df.to_sql("raw_data", self.conn, index=False, if_exists="replace")

        return df

    def get_raw_data(self) -> pd.DataFrame:
        """Retorna os dados da tabela raw_data."""
        return pd.read_sql("SELECT * FROM raw_data", self.conn)

    def get_clean_data(self) -> Optional[pd.DataFrame]:
        """Retorna os dados da tabela clean_data, se existir."""
        try:
            return pd.read_sql("SELECT * FROM clean_data", self.conn)
        except Exception:
            return None

    def execute_cleaning_sql(self, sql: str) -> bool:
        """
        Executa uma query SQL de limpeza.

        Args:
            sql: Query SQL para criar/popular a tabela clean_data

        Returns:
            True se executado com sucesso

        Raises:
            sqlite3.Error: Se a query for inválida
        """
        # Executa a query (pode ser múltiplas statements separadas por ;)
        self.cursor.executescript(sql)
        self.conn.commit()
        return True

    def get_table_info(self, table_name: str = "raw_data") -> list:
        """Retorna informações sobre as colunas de uma tabela."""
        self.cursor.execute(f"PRAGMA table_info({table_name})")
        return self.cursor.fetchall()

    def get_sample_rows(self, table_name: str = "raw_data", n: int = 5) -> pd.DataFrame:
        """Retorna as primeiras n linhas de uma tabela."""
        return pd.read_sql(f"SELECT * FROM {table_name} LIMIT {n}", self.conn)

    def close(self):
        """Fecha a conexão com o banco de dados."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
