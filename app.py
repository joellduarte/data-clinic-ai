"""
Data Clinic AI - Interface Principal
Pipeline de ETL Inteligente com LLMs para Higienização de Dados
"""

import streamlit as st
import pandas as pd

from src.database import DataManager
from src.sanitizer import DataSanitizer

# Configuração da página
st.set_page_config(
    page_title="Data Clinic AI",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS customizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E88E5;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        margin-top: 0;
    }
    .log-entry {
        font-family: monospace;
        font-size: 0.85rem;
        padding: 0.3rem 0;
        border-bottom: 1px solid #eee;
    }
    .log-timestamp {
        color: #888;
        margin-right: 0.5rem;
    }
    .log-stage {
        font-weight: bold;
        padding: 0.1rem 0.4rem;
        border-radius: 3px;
        margin-right: 0.5rem;
    }
    .stage-analysis { background-color: #E3F2FD; color: #1565C0; }
    .stage-sql_gen { background-color: #F3E5F5; color: #7B1FA2; }
    .stage-sql_exec { background-color: #E8F5E9; color: #2E7D32; }
    .stage-retry { background-color: #FFF3E0; color: #EF6C00; }
    .stage-error { background-color: #FFEBEE; color: #C62828; }
    .stage-pipeline { background-color: #E0F7FA; color: #00838F; }
    .retry-badge {
        background-color: #FFF3E0;
        color: #E65100;
        padding: 0.2rem 0.5rem;
        border-radius: 10px;
        font-size: 0.8rem;
        margin-left: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Inicializa variáveis de sessão."""
    if "data_manager" not in st.session_state:
        st.session_state.data_manager = None
    if "sanitizer" not in st.session_state:
        st.session_state.sanitizer = None
    if "raw_df" not in st.session_state:
        st.session_state.raw_df = None
    if "clean_df" not in st.session_state:
        st.session_state.clean_df = None
    if "analysis_result" not in st.session_state:
        st.session_state.analysis_result = None
    if "cleaning_result" not in st.session_state:
        st.session_state.cleaning_result = None


def render_logs(logs):
    """Renderiza os logs de forma visual."""
    if not logs:
        st.info("Nenhum log disponível ainda.")
        return

    for log in logs:
        stage_class = f"stage-{log.stage}"
        html = f"""
        <div class="log-entry">
            <span class="log-timestamp">[{log.timestamp}]</span>
            <span class="log-stage {stage_class}">{log.stage.upper()}</span>
            <span>{log.message}</span>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)

        if log.details:
            with st.expander("Ver detalhes", expanded=False):
                st.text(log.details)


def main():
    init_session_state()

    # Header
    st.markdown('<p class="main-header">🏥 Data Clinic AI</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Pipeline de ETL Inteligente para Higienização de Dados</p>', unsafe_allow_html=True)
    st.markdown("---")

    # Sidebar
    with st.sidebar:
        st.header("📋 Instruções")
        st.markdown("""
        1. **Upload**: Carregue um CSV com dados "sujos"
        2. **Diagnosticar**: IA analisa a estrutura dos dados
        3. **Higienizar**: IA gera e executa SQL de limpeza
        4. **Download**: Baixe os dados limpos
        """)

        st.markdown("---")
        st.header("🤖 Modelos Utilizados")
        st.markdown("""
        - **Análise**: Llama 3.3 70B
        - **SQL Gen**: DeepSeek R1
        """)

        st.markdown("---")
        st.header("⚙️ Configurações")
        st.markdown(f"**Max Retries**: {DataSanitizer.MAX_RETRIES}")
        st.caption("Se o SQL gerado falhar, a IA tenta corrigir automaticamente.")

        st.markdown("---")
        st.caption("Desenvolvido por Joel Duarte")

    # Upload de arquivo
    st.header("1️⃣ Upload do CSV")
    uploaded_file = st.file_uploader(
        "Arraste ou selecione um arquivo CSV",
        type=["csv"],
        help="Carregue um arquivo CSV com dados que precisam de limpeza"
    )

    if uploaded_file is not None:
        # Carrega o arquivo
        if st.session_state.data_manager is None or st.button("🔄 Recarregar arquivo", type="secondary"):
            with st.spinner("Carregando dados..."):
                st.session_state.data_manager = DataManager()
                st.session_state.raw_df = st.session_state.data_manager.load_csv_to_raw(uploaded_file)
                st.session_state.sanitizer = DataSanitizer(st.session_state.data_manager)
                # Reset estados anteriores
                st.session_state.analysis_result = None
                st.session_state.cleaning_result = None
                st.session_state.clean_df = None

        # Exibe dados originais
        st.header("2️⃣ Dados Originais (Sujos)")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Linhas", len(st.session_state.raw_df))
        with col2:
            st.metric("Colunas", len(st.session_state.raw_df.columns))
        with col3:
            st.metric("Células vazias", st.session_state.raw_df.isna().sum().sum())

        st.dataframe(
            st.session_state.raw_df,
            use_container_width=True,
            height=300
        )

        # Botão de diagnóstico
        st.header("3️⃣ Diagnóstico com IA")

        col_diag1, col_diag2 = st.columns([1, 3])
        with col_diag1:
            diagnose_btn = st.button("🔍 Diagnosticar com IA", type="primary", use_container_width=True)

        if diagnose_btn:
            with st.spinner("🤖 Llama 3.3 analisando estrutura dos dados..."):
                st.session_state.analysis_result = st.session_state.sanitizer.analyze()

        # Mostra resultado da análise
        if st.session_state.analysis_result is not None:
            if st.session_state.analysis_result.success:
                st.success("✅ Análise concluída!")

                with st.expander("📊 Ver Diagnóstico Completo", expanded=True):
                    analysis = st.session_state.analysis_result.analysis

                    if isinstance(analysis, dict) and "error" not in analysis:
                        for col_name, col_info in analysis.items():
                            with st.container():
                                st.markdown(f"**Coluna: `{col_name}`**")
                                if isinstance(col_info, dict):
                                    st.markdown(f"- Tipo: `{col_info.get('tipo_identificado', 'N/A')}`")

                                    problemas = col_info.get('problemas', [])
                                    if problemas:
                                        st.markdown(f"- Problemas: {', '.join(problemas) if isinstance(problemas, list) else problemas}")

                                    sugestao = col_info.get('sugestao_limpeza', '')
                                    if sugestao:
                                        st.markdown(f"- Sugestão: {sugestao}")
                                st.markdown("---")
                    else:
                        st.json(analysis)
            else:
                st.error(f"❌ Erro na análise: {st.session_state.analysis_result.error}")

        # Botão de higienização
        st.header("4️⃣ Higienização dos Dados")

        # Só habilita se tiver análise
        can_clean = st.session_state.analysis_result is not None and st.session_state.analysis_result.success

        col_clean1, col_clean2 = st.columns([1, 3])
        with col_clean1:
            clean_btn = st.button(
                "🧹 Higienizar Dados",
                type="primary",
                use_container_width=True,
                disabled=not can_clean
            )

        if not can_clean:
            st.info("💡 Execute o diagnóstico primeiro para habilitar a higienização.")

        if clean_btn and can_clean:
            with st.spinner("🤖 DeepSeek R1 gerando SQL de limpeza..."):
                st.session_state.cleaning_result = st.session_state.sanitizer.clean()

                if st.session_state.cleaning_result.success:
                    st.session_state.clean_df = st.session_state.cleaning_result.clean_data

        # Mostra resultado da limpeza
        if st.session_state.cleaning_result is not None:
            if st.session_state.cleaning_result.success:
                # Mensagem de sucesso com badge de retries se aplicável
                success_msg = "✅ Dados higienizados com sucesso!"
                if st.session_state.cleaning_result.retries > 0:
                    success_msg += f' <span class="retry-badge">🔄 {st.session_state.cleaning_result.retries} correções automáticas</span>'
                st.markdown(success_msg, unsafe_allow_html=True)

                # Tabs para resultado e logs
                tab_data, tab_sql, tab_reasoning, tab_logs = st.tabs([
                    "📊 Dados Limpos",
                    "💻 SQL Gerado",
                    "🧠 Raciocínio da IA",
                    "📜 Logs de Execução"
                ])

                with tab_data:
                    st.subheader("Dados Limpos")

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Linhas", len(st.session_state.clean_df))
                    with col2:
                        st.metric("Colunas", len(st.session_state.clean_df.columns))
                    with col3:
                        st.metric("Células vazias", st.session_state.clean_df.isna().sum().sum())
                    with col4:
                        original_empty = st.session_state.raw_df.isna().sum().sum()
                        current_empty = st.session_state.clean_df.isna().sum().sum()
                        delta = current_empty - original_empty
                        st.metric("Vazias (delta)", delta, delta_color="inverse")

                    st.dataframe(
                        st.session_state.clean_df,
                        use_container_width=True,
                        height=300
                    )

                    # Botão de download
                    csv_data = st.session_state.clean_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download CSV Limpo",
                        data=csv_data,
                        file_name="dados_limpos.csv",
                        mime="text/csv",
                        type="primary"
                    )

                with tab_sql:
                    st.subheader("SQL Executado")
                    if st.session_state.cleaning_result.retries > 0:
                        st.warning(f"⚠️ O SQL original falhou e foi corrigido {st.session_state.cleaning_result.retries}x automaticamente.")
                    st.code(st.session_state.cleaning_result.sql_executed, language="sql")

                with tab_reasoning:
                    st.subheader("Raciocínio do DeepSeek R1")
                    st.caption("O processo de pensamento (Chain of Thought) da IA ao gerar o SQL:")
                    reasoning = st.session_state.cleaning_result.reasoning or "Sem raciocínio disponível"
                    st.markdown(reasoning)

                with tab_logs:
                    st.subheader("Logs de Execução")
                    st.caption("Timeline detalhada do processo de higienização:")
                    render_logs(st.session_state.cleaning_result.logs)

            else:
                st.error(f"❌ Erro na limpeza: {st.session_state.cleaning_result.error}")

                # Mostra detalhes mesmo em caso de erro
                tab_sql_err, tab_logs_err = st.tabs(["💻 SQL que falhou", "📜 Logs"])

                with tab_sql_err:
                    if st.session_state.cleaning_result.sql_executed:
                        st.code(st.session_state.cleaning_result.sql_executed, language="sql")
                    else:
                        st.info("Nenhum SQL foi gerado.")

                    if st.session_state.cleaning_result.reasoning:
                        with st.expander("Ver raciocínio da IA"):
                            st.markdown(st.session_state.cleaning_result.reasoning)

                with tab_logs_err:
                    render_logs(st.session_state.cleaning_result.logs)

        # Seção de Logs Gerais (sempre visível após upload)
        st.markdown("---")
        with st.expander("📜 Ver Todos os Logs da Sessão", expanded=False):
            if st.session_state.sanitizer:
                all_logs = st.session_state.sanitizer.get_logs()
                if all_logs:
                    render_logs(all_logs)
                else:
                    st.info("Execute o diagnóstico ou higienização para gerar logs.")
            else:
                st.info("Carregue um arquivo para começar.")


if __name__ == "__main__":
    main()
