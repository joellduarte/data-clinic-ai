"""
Data Clinic AI - Orquestrador de Limpeza
Coordena o fluxo: CSV -> Análise IA -> SQL -> Dados Limpos
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import pandas as pd

from .database import DataManager
from .llm_client import analyze_schema, generate_cleaning_sql, fix_sql_error


@dataclass
class LogEntry:
    """Entrada de log do processo."""
    timestamp: str
    stage: str  # "analysis", "sql_gen", "sql_exec", "retry", "error"
    message: str
    details: Optional[str] = None


@dataclass
class CleaningResult:
    """Resultado do processo de limpeza."""
    success: bool
    clean_data: Optional[pd.DataFrame] = None
    sql_executed: Optional[str] = None
    reasoning: Optional[str] = None
    error: Optional[str] = None
    retries: int = 0
    logs: list[LogEntry] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Resultado da análise de schema."""
    success: bool
    analysis: Optional[dict] = None
    raw_response: Optional[str] = None
    error: Optional[str] = None
    logs: list[LogEntry] = field(default_factory=list)


class DataSanitizer:
    """
    Orquestra o pipeline de limpeza de dados.
    Conecta o DataManager com os clientes LLM.
    Implementa retry logic para SQL inválido.
    """

    MAX_RETRIES = 2  # Número máximo de tentativas de correção

    def __init__(self, data_manager: DataManager):
        self.dm = data_manager
        self.last_analysis: Optional[AnalysisResult] = None
        self.last_cleaning: Optional[CleaningResult] = None
        self.logs: list[LogEntry] = []

    def _log(self, stage: str, message: str, details: Optional[str] = None):
        """Adiciona entrada ao log."""
        entry = LogEntry(
            timestamp=datetime.now().strftime("%H:%M:%S"),
            stage=stage,
            message=message,
            details=details
        )
        self.logs.append(entry)
        return entry

    def get_logs(self) -> list[LogEntry]:
        """Retorna todos os logs da sessão."""
        return self.logs

    def clear_logs(self):
        """Limpa os logs."""
        self.logs = []

    def analyze(self) -> AnalysisResult:
        """
        Executa análise do schema usando Llama 3.3.

        Returns:
            AnalysisResult com diagnóstico das colunas
        """
        logs = []

        try:
            self._log("analysis", "Iniciando análise de schema com Llama 3.3 70B")

            # Pega amostra dos dados
            sample_df = self.dm.get_sample_rows("raw_data", n=5)
            column_names = list(sample_df.columns)
            sample_str = sample_df.to_string(index=False)

            logs.append(self._log(
                "analysis",
                f"Analisando {len(column_names)} colunas",
                f"Colunas: {', '.join(column_names)}"
            ))

            # Chama o LLM para análise
            result = analyze_schema(sample_str, column_names)

            logs.append(self._log(
                "analysis",
                "Análise concluída com sucesso",
                f"Modelo: {result.get('model', 'N/A')}"
            ))

            self.last_analysis = AnalysisResult(
                success=True,
                analysis=result.get("analysis"),
                raw_response=result.get("raw_response"),
                logs=logs,
            )

        except Exception as e:
            logs.append(self._log("error", f"Erro na análise: {str(e)}"))
            self.last_analysis = AnalysisResult(
                success=False,
                error=str(e),
                logs=logs,
            )

        return self.last_analysis

    def clean(self, analysis: Optional[dict] = None) -> CleaningResult:
        """
        Gera e executa SQL de limpeza usando DeepSeek R1.
        Implementa retry logic para corrigir erros de SQL.

        Args:
            analysis: Análise prévia (usa last_analysis se não fornecido)

        Returns:
            CleaningResult com dados limpos ou erro
        """
        logs = []
        retries = 0
        sql_code = ""
        reasoning = ""

        try:
            # Usa análise prévia se não fornecida
            if analysis is None:
                if self.last_analysis is None or not self.last_analysis.success:
                    return CleaningResult(
                        success=False,
                        error="Execute a análise primeiro (analyze)"
                    )
                analysis = self.last_analysis.analysis

            # Pega dados para contexto
            sample_df = self.dm.get_sample_rows("raw_data", n=5)
            column_names = list(sample_df.columns)
            sample_str = sample_df.to_string(index=False)

            logs.append(self._log("sql_gen", "Gerando SQL de limpeza com DeepSeek R1"))

            # Gera SQL com DeepSeek
            sql_result = generate_cleaning_sql(
                {"analysis": analysis},
                column_names,
                sample_str
            )

            sql_code = sql_result.get("sql", "")
            reasoning = sql_result.get("reasoning", "")

            logs.append(self._log(
                "sql_gen",
                "SQL gerado com sucesso",
                f"Tamanho: {len(sql_code)} caracteres"
            ))

            if not sql_code:
                logs.append(self._log("error", "LLM não retornou SQL"))
                return CleaningResult(
                    success=False,
                    error="LLM não gerou SQL válido",
                    reasoning=reasoning,
                    logs=logs,
                )

            # Tenta executar o SQL com retry logic
            last_error = None
            while retries <= self.MAX_RETRIES:
                try:
                    logs.append(self._log(
                        "sql_exec",
                        f"Executando SQL (tentativa {retries + 1}/{self.MAX_RETRIES + 1})"
                    ))

                    # Executa o SQL
                    self.dm.execute_cleaning_sql(sql_code)

                    # Recupera dados limpos
                    clean_data = self.dm.get_clean_data()

                    if clean_data is None or clean_data.empty:
                        raise ValueError("Tabela clean_data está vazia após execução")

                    logs.append(self._log(
                        "sql_exec",
                        f"SQL executado com sucesso! {len(clean_data)} linhas limpas",
                        f"Retries necessários: {retries}"
                    ))

                    self.last_cleaning = CleaningResult(
                        success=True,
                        clean_data=clean_data,
                        sql_executed=sql_code,
                        reasoning=reasoning,
                        retries=retries,
                        logs=logs,
                    )
                    return self.last_cleaning

                except Exception as exec_error:
                    last_error = str(exec_error)
                    logs.append(self._log(
                        "error",
                        f"Erro ao executar SQL: {last_error[:100]}..."
                    ))

                    if retries < self.MAX_RETRIES:
                        retries += 1
                        logs.append(self._log(
                            "retry",
                            f"Solicitando correção do SQL (retry {retries}/{self.MAX_RETRIES})"
                        ))

                        # Pede para IA corrigir
                        fix_result = fix_sql_error(sql_code, last_error, column_names)
                        sql_code = fix_result.get("sql", "")
                        fix_reasoning = fix_result.get("reasoning", "")

                        logs.append(self._log(
                            "retry",
                            "SQL corrigido recebido",
                            f"Correção: {fix_reasoning[:200]}..."
                        ))

                        # Acumula o raciocínio
                        reasoning += f"\n\n--- CORREÇÃO (Retry {retries}) ---\n{fix_reasoning}"
                    else:
                        break

            # Se chegou aqui, esgotou retries
            logs.append(self._log(
                "error",
                f"Falha após {self.MAX_RETRIES + 1} tentativas",
                f"Último erro: {last_error}"
            ))

            self.last_cleaning = CleaningResult(
                success=False,
                error=f"SQL inválido após {retries} correções: {last_error}",
                sql_executed=sql_code,
                reasoning=reasoning,
                retries=retries,
                logs=logs,
            )

        except Exception as e:
            logs.append(self._log("error", f"Erro inesperado: {str(e)}"))
            self.last_cleaning = CleaningResult(
                success=False,
                error=str(e),
                sql_executed=sql_code if sql_code else None,
                reasoning=reasoning if reasoning else None,
                retries=retries,
                logs=logs,
            )

        return self.last_cleaning

    def run_pipeline(self) -> CleaningResult:
        """
        Executa o pipeline completo: análise + limpeza.

        Returns:
            CleaningResult final
        """
        self.clear_logs()
        self._log("pipeline", "Iniciando pipeline completo de higienização")

        # Passo 1: Análise
        analysis_result = self.analyze()
        if not analysis_result.success:
            return CleaningResult(
                success=False,
                error=f"Falha na análise: {analysis_result.error}",
                logs=self.logs,
            )

        # Passo 2: Limpeza
        return self.clean()
