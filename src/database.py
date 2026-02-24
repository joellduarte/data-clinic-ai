"""
Data Clinic AI - Gerenciamento de Banco de Dados SQLite
Responsável por carregar CSVs para tabelas temporárias em memória.
"""

import sqlite3
import pandas as pd
from typing import Optional, List
import io
import tempfile
import os


class DataManager:
    """
    Gerencia operações de banco de dados SQLite em memória.
    Carrega CSVs para tabelas temporárias e executa queries de limpeza.
    """

    def __init__(self):
        """Inicializa conexão SQLite em memória."""
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.cursor = self.conn.cursor()

    def load_csv_to_raw(self, file, separator: str = ",", encoding: str = "utf-8") -> pd.DataFrame:
        """
        Carrega um arquivo CSV para a tabela 'raw_data' no SQLite.

        Args:
            file: Arquivo CSV (pode ser path, file-like object ou UploadedFile do Streamlit)
            separator: Caractere separador do CSV (vírgula, ponto-e-vírgula, tab, etc.)
            encoding: Encoding do arquivo (utf-8, latin-1, etc.)

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
                content = content.decode(encoding)
            df = pd.read_csv(io.StringIO(content), sep=separator)
        else:
            # Path de arquivo
            df = pd.read_csv(file, sep=separator, encoding=encoding)

        if df.empty:
            raise ValueError("O arquivo CSV está vazio")

        # Remove tabela anterior se existir
        self.cursor.execute("DROP TABLE IF EXISTS raw_data")
        self.cursor.execute("DROP TABLE IF EXISTS clean_data")

        # Carrega DataFrame para SQLite
        df.to_sql("raw_data", self.conn, index=False, if_exists="replace")

        return df

    def load_excel_to_raw(self, file, sheet_name=0) -> pd.DataFrame:
        """
        Carrega um arquivo Excel para a tabela 'raw_data' no SQLite.

        Args:
            file: Arquivo Excel (pode ser path, file-like object ou UploadedFile do Streamlit)
            sheet_name: Nome ou índice da sheet a ser carregada (default: primeira sheet)

        Returns:
            DataFrame com os dados carregados

        Raises:
            ValueError: Se o arquivo estiver vazio ou inválido
        """
        # Lê o Excel para DataFrame
        if hasattr(file, 'read'):
            # File-like object (ex: UploadedFile do Streamlit)
            content = file.read()
            df = pd.read_excel(io.BytesIO(content), sheet_name=sheet_name, engine='openpyxl')
        else:
            # Path de arquivo
            df = pd.read_excel(file, sheet_name=sheet_name, engine='openpyxl')

        if df.empty:
            raise ValueError("O arquivo Excel está vazio")

        # Remove tabela anterior se existir
        self.cursor.execute("DROP TABLE IF EXISTS raw_data")
        self.cursor.execute("DROP TABLE IF EXISTS clean_data")

        # Carrega DataFrame para SQLite
        df.to_sql("raw_data", self.conn, index=False, if_exists="replace")

        return df

    def load_db_to_raw(self, file, table_name: str) -> pd.DataFrame:
        """
        Carrega uma tabela de um arquivo SQLite (.db) para 'raw_data' na memória.

        Args:
            file: Arquivo SQLite (pode ser path, file-like object ou UploadedFile do Streamlit)
            table_name: Nome da tabela a ser carregada do arquivo .db

        Returns:
            DataFrame com os dados carregados

        Raises:
            ValueError: Se a tabela estiver vazia ou não existir
        """
        temp_path = None
        try:
            # Se for file-like object, salva em arquivo temporário
            if hasattr(file, 'read'):
                content = file.read()
                with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
                    tmp.write(content)
                    temp_path = tmp.name
                db_path = temp_path
            else:
                db_path = file

            # Conecta ao banco de dados do arquivo
            source_conn = sqlite3.connect(db_path)
            try:
                # Lê a tabela do arquivo .db
                df = pd.read_sql(f"SELECT * FROM {table_name}", source_conn)
            finally:
                source_conn.close()

            if df.empty:
                raise ValueError(f"A tabela '{table_name}' está vazia")

            # Remove tabela anterior se existir
            self.cursor.execute("DROP TABLE IF EXISTS raw_data")
            self.cursor.execute("DROP TABLE IF EXISTS clean_data")

            # Carrega DataFrame para SQLite em memória
            df.to_sql("raw_data", self.conn, index=False, if_exists="replace")

            return df

        finally:
            # Remove arquivo temporário se foi criado
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def list_tables_from_db(self, file) -> List[str]:
        """
        Lista as tabelas disponíveis em um arquivo SQLite (.db).

        Args:
            file: Arquivo SQLite (pode ser path, file-like object ou UploadedFile do Streamlit)

        Returns:
            Lista com os nomes das tabelas disponíveis

        Raises:
            ValueError: Se não houver tabelas no arquivo
        """
        temp_path = None
        try:
            # Se for file-like object, salva em arquivo temporário
            if hasattr(file, 'read'):
                content = file.read()
                # Reseta o ponteiro do arquivo para permitir leituras futuras
                if hasattr(file, 'seek'):
                    file.seek(0)
                with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
                    tmp.write(content)
                    temp_path = tmp.name
                db_path = temp_path
            else:
                db_path = file

            # Conecta ao banco de dados do arquivo
            source_conn = sqlite3.connect(db_path)
            try:
                cursor = source_conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                tables = [row[0] for row in cursor.fetchall()]
            finally:
                source_conn.close()

            if not tables:
                raise ValueError("O arquivo SQLite não contém tabelas")

            return tables

        finally:
            # Remove arquivo temporário se foi criado
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def list_sheets_from_excel(self, file) -> List[str]:
        """
        Lista as sheets disponíveis em um arquivo Excel.

        Args:
            file: Arquivo Excel (pode ser path, file-like object ou UploadedFile do Streamlit)

        Returns:
            Lista com os nomes das sheets disponíveis

        Raises:
            ValueError: Se não houver sheets no arquivo
        """
        # Lê as sheets do arquivo Excel
        if hasattr(file, 'read'):
            content = file.read()
            # Reseta o ponteiro do arquivo para permitir leituras futuras
            if hasattr(file, 'seek'):
                file.seek(0)
            excel_file = pd.ExcelFile(io.BytesIO(content), engine='openpyxl')
        else:
            excel_file = pd.ExcelFile(file, engine='openpyxl')

        sheets = excel_file.sheet_names

        if not sheets:
            raise ValueError("O arquivo Excel não contém sheets")

        return sheets

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
