"""
Data Clinic AI - Interface Principal
Pipeline de ETL Inteligente com LLMs para Higienização de Dados
"""

import streamlit as st
import pandas as pd

from src.database import DataManager
from src.sanitizer import DataSanitizer
from src import llm_client
from src import config

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
    .plan-free {
        background-color: #1B5E20;
        color: #FFFFFF;
        padding: 0.5rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
        text-align: center;
    }
    .plan-paid {
        background-color: #E65100;
        color: #FFFFFF;
        padding: 0.5rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
        text-align: center;
    }
    .price-tag {
        font-size: 0.75rem;
        color: #666;
    }
</style>
""", unsafe_allow_html=True)

# Mapeamento de separadores
SEPARATORS = {
    "Vírgula (,)": ",",
    "Ponto e vírgula (;)": ";",
    "Tab (\\t)": "\t",
    "Pipe (|)": "|",
}

ENCODINGS = {
    "UTF-8": "utf-8",
    "Latin-1 (ISO-8859-1)": "latin-1",
    "Windows-1252": "cp1252",
}


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
    if "file_loaded" not in st.session_state:
        st.session_state.file_loaded = False
    if "current_plan" not in st.session_state:
        st.session_state.current_plan = "free"
    if "show_plan_confirm" not in st.session_state:
        st.session_state.show_plan_confirm = False
    if "pending_plan" not in st.session_state:
        st.session_state.pending_plan = None
    if "custom_analysis_model" not in st.session_state:
        st.session_state.custom_analysis_model = ""
    if "custom_sql_model" not in st.session_state:
        st.session_state.custom_sql_model = ""


def reset_data_state():
    """Reseta o estado dos dados ao trocar de modelo/plano."""
    st.session_state.data_manager = None
    st.session_state.sanitizer = None
    st.session_state.raw_df = None
    st.session_state.clean_df = None
    st.session_state.analysis_result = None
    st.session_state.cleaning_result = None
    st.session_state.file_loaded = False


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


def format_error_message(error: str) -> tuple[str, str]:
    """
    Formata mensagem de erro para exibição amigável.
    Retorna (mensagem_formatada, tipo: "warning" ou "error")
    """
    if "429" in error or "rate" in error.lower():
        return (
            "Limite diário de requisições gratuitas atingido! "
            "O OpenRouter permite 50 requisições/dia para modelos gratuitos. "
            "O limite reseta à meia-noite (UTC). Amanhã você pode continuar testando, "
            "ou adicione créditos em openrouter.ai/credits para desbloquear mais requisições.",
            "warning"
        )
    if "402" in error or "spend limit" in error.lower():
        return (
            "Sem créditos na conta OpenRouter. "
            "Adicione créditos em openrouter.ai/credits para usar modelos pagos.",
            "warning"
        )
    if "401" in error or "unauthorized" in error.lower():
        return (
            "Erro de autenticação. Verifique sua API Key nas Configurações (sidebar).",
            "error"
        )
    if "timeout" in error.lower():
        return (
            "Timeout. O modelo demorou muito para responder. Tente novamente.",
            "error"
        )
    return error, "error"


def render_plan_selector():
    """Renderiza o seletor de plano na sidebar."""
    st.header("💳 Modelo de agente")

    current_plan = st.session_state.current_plan
    free_info = llm_client.get_plan_info("free")
    paid_info = llm_client.get_plan_info("paid")

    # Mostra plano atual
    if current_plan == "free":
        st.markdown('<div class="plan-free">✅ <b>Plano Gratuito</b> ativo</div>', unsafe_allow_html=True)
    elif current_plan == "paid":
        st.markdown('<div class="plan-paid">💰 <b>Plano Pago</b> ativo</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="plan-paid">🔧 <b>Personalizado</b> ativo</div>', unsafe_allow_html=True)

    # Seletor de plano
    plan_options = {
        "Gratuito (Free)": "free",
        "Pago (Paid)": "paid",
        "Personalizado (Custom)": "custom",
    }

    # Determina índice atual
    plan_index = {"free": 0, "paid": 1, "custom": 2}.get(current_plan, 0)

    selected_label = st.selectbox(
        "Selecione o plano",
        options=list(plan_options.keys()),
        index=plan_index,
        key="plan_selector"
    )
    selected_plan = plan_options[selected_label]

    # Se mudou de plano, pede confirmação
    if selected_plan != current_plan:
        st.session_state.pending_plan = selected_plan
        st.session_state.show_plan_confirm = True

    # Modal de confirmação para mudar para pago
    if st.session_state.show_plan_confirm and st.session_state.pending_plan == "paid":
        st.warning("⚠️ **Confirmar mudança para plano Pago?**")
        st.markdown("""
        **Custos estimados por requisição:**

        | Modelo | Input | Output |
        |--------|-------|--------|
        | GPT-4o-mini (Análise) | $0.15/M tokens | $0.60/M tokens |
        | DeepSeek V3 (SQL) | $0.19/M tokens | $0.87/M tokens |

        *Custo típico por arquivo: ~$0.001 a $0.01*
        """)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Confirmar", type="primary", use_container_width=True):
                llm_client.set_plan("paid")
                st.session_state.current_plan = "paid"
                st.session_state.show_plan_confirm = False
                st.session_state.pending_plan = None
                reset_data_state()
                st.rerun()
        with col2:
            if st.button("❌ Cancelar", use_container_width=True):
                st.session_state.show_plan_confirm = False
                st.session_state.pending_plan = None
                st.rerun()

    # Confirmação para voltar ao gratuito
    elif st.session_state.show_plan_confirm and st.session_state.pending_plan == "free":
        st.info("Voltar para o plano **Gratuito**?")
        st.caption("Modelos gratuitos têm rate limit compartilhado.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Confirmar", type="primary", use_container_width=True):
                llm_client.set_plan("free")
                st.session_state.current_plan = "free"
                st.session_state.show_plan_confirm = False
                st.session_state.pending_plan = None
                reset_data_state()
                st.rerun()
        with col2:
            if st.button("❌ Cancelar", use_container_width=True):
                st.session_state.show_plan_confirm = False
                st.session_state.pending_plan = None
                st.rerun()

    # Confirmação para plano personalizado
    elif st.session_state.show_plan_confirm and st.session_state.pending_plan == "custom":
        st.info("Mudar para plano **Personalizado**?")
        st.caption("Você poderá definir os modelos manualmente.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Confirmar", type="primary", use_container_width=True):
                llm_client.set_plan("custom")
                st.session_state.current_plan = "custom"
                st.session_state.show_plan_confirm = False
                st.session_state.pending_plan = None
                reset_data_state()
                st.rerun()
        with col2:
            if st.button("❌ Cancelar", use_container_width=True):
                st.session_state.show_plan_confirm = False
                st.session_state.pending_plan = None
                st.rerun()

    # Detalhes dos modelos
    with st.expander("📋 Detalhes dos modelos"):
        st.markdown("**Plano Gratuito:**")
        st.markdown(f"- Análise: `{free_info['analysis']}`")
        st.markdown(f"- SQL: `{free_info['sql_gen']}`")
        st.caption("Rate limit compartilhado entre usuários")

        st.markdown("---")
        st.markdown("**Plano Pago:**")
        st.markdown(f"- Análise: `{paid_info['analysis']}`")
        st.caption("$0.15/M input, $0.60/M output")
        st.markdown(f"- SQL: `{paid_info['sql_gen']}`")
        st.caption("$0.19/M input, $0.87/M output")

        st.markdown("---")
        st.markdown("**Plano Personalizado:**")
        st.caption("Cole o ID do modelo do OpenRouter (ex: `openai/gpt-4o`)")


def main():
    init_session_state()

    # Sincroniza o plano com o llm_client
    llm_client.set_plan(st.session_state.current_plan)

    # Header
    st.markdown('<p class="main-header">🏥 Data Clinic AI</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Pipeline de ETL Inteligente para Higienização de Dados</p>', unsafe_allow_html=True)

    # Botão de reset no topo (só aparece se tiver arquivo carregado)
    if st.session_state.file_loaded:
        col_reset_top, col_empty = st.columns([1, 4])
        with col_reset_top:
            if st.button("🔄 Resetar Dados", key="reset_top", help="Limpa todos os dados e volta ao estado inicial"):
                reset_data_state()
                st.rerun()

    st.markdown("---")

    # Sidebar
    with st.sidebar:
        # 1. Instruções (primeiro)
        st.header("📋 Instruções")
        st.markdown("""
        1. **Upload**: Carregue um CSV
        2. **Configurar**: Separador e encoding
        3. **Diagnosticar**: IA analisa os dados
        4. **Higienizar**: IA gera SQL de limpeza
        5. **Download**: Baixe o resultado
        """)

        st.markdown("---")

        # 2. Modelo de agentes (seletor de plano)
        render_plan_selector()

        st.markdown("---")

        # 3. Modelos em Uso
        st.header("🤖 Modelos em Uso")

        if st.session_state.current_plan == "custom":
            # Campos de input para modelos personalizados
            st.caption("**Plano: Personalizado**")

            custom_analysis = st.text_input(
                "Análise:",
                value=st.session_state.custom_analysis_model,
                placeholder="ex: openai/gpt-4o-mini",
                key="input_analysis_model",
                help="ID do modelo para análise de schema"
            )

            custom_sql = st.text_input(
                "SQL:",
                value=st.session_state.custom_sql_model,
                placeholder="ex: deepseek/deepseek-chat",
                key="input_sql_model",
                help="ID do modelo para geração de SQL"
            )

            # Salva os modelos personalizados e reseta dados se mudou
            if custom_analysis != st.session_state.custom_analysis_model or custom_sql != st.session_state.custom_sql_model:
                st.session_state.custom_analysis_model = custom_analysis
                st.session_state.custom_sql_model = custom_sql
                llm_client.set_custom_models(custom_analysis, custom_sql)
                # Reseta dados ao trocar modelo personalizado
                if st.session_state.file_loaded:
                    reset_data_state()
                    st.rerun()

            # Aplica os modelos atuais
            llm_client.set_custom_models(
                st.session_state.custom_analysis_model,
                st.session_state.custom_sql_model
            )

            st.caption("[Ver modelos disponíveis](https://openrouter.ai/models)")
        else:
            models = llm_client.get_current_models()
            plan_names = {"free": "Gratuito", "paid": "Pago"}
            plan_name = plan_names.get(st.session_state.current_plan, "Personalizado")
            st.caption(f"**Plano: {plan_name}**")
            st.markdown(f"- Análise: `{models['analysis'].split('/')[-1]}`")
            st.markdown(f"- SQL: `{models['sql_gen'].split('/')[-1]}`")

        st.markdown("---")

        # 4. Configurações (último)
        st.header("⚙️ Configurações")

        # API Key do OpenRouter
        current_api_key = config.get_api_key()

        if current_api_key:
            st.caption(f"✅ API Key configurada: ••••••••{current_api_key[-8:]}")

        new_api_key = st.text_input(
            "API Key OpenRouter",
            value="",
            type="password",
            placeholder="sk-or-v1-...",
            help="Sua chave de API do OpenRouter. Salva localmente no arquivo config.local.json (não vai para o GitHub)."
        )

        if st.button("💾 Salvar API Key", disabled=not new_api_key):
            config.set_api_key(new_api_key)
            llm_client.refresh_client()
            st.success("API Key salva!")
            st.rerun()

        if not current_api_key:
            st.caption("⚠️ Configure sua API Key para usar o sistema")

        # Max Retries
        current_retries = config.get_max_retries()
        new_retries = st.number_input(
            "Max Retries",
            min_value=0,
            max_value=10,
            value=current_retries,
            help="Número máximo de tentativas de correção automática quando o SQL gerado falha. Se o SQL der erro, o sistema pede para a IA corrigir até X vezes antes de reportar falha."
        )

        if new_retries != current_retries:
            config.set_max_retries(new_retries)
            st.rerun()

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
        # Opções de configuração do CSV
        st.subheader("Configurações do arquivo")
        col_sep, col_enc = st.columns(2)

        with col_sep:
            separator_label = st.selectbox(
                "Separador",
                options=list(SEPARATORS.keys()),
                index=0,
                help="Caractere que separa as colunas no CSV"
            )
            separator = SEPARATORS[separator_label]

        with col_enc:
            encoding_label = st.selectbox(
                "Encoding",
                options=list(ENCODINGS.keys()),
                index=0,
                help="Codificação do arquivo (use Latin-1 se UTF-8 der erro)"
            )
            encoding = ENCODINGS[encoding_label]

        # Botão para carregar
        load_btn = st.button("📂 Carregar arquivo", type="primary")

        if load_btn or (st.session_state.file_loaded and st.session_state.raw_df is not None):
            if load_btn:
                try:
                    with st.spinner("Carregando dados..."):
                        st.session_state.data_manager = DataManager()
                        st.session_state.raw_df = st.session_state.data_manager.load_csv_to_raw(
                            uploaded_file,
                            separator=separator,
                            encoding=encoding
                        )
                        st.session_state.sanitizer = DataSanitizer(st.session_state.data_manager)
                        st.session_state.file_loaded = True
                        st.session_state.analysis_result = None
                        st.session_state.cleaning_result = None
                        st.session_state.clean_df = None
                except UnicodeDecodeError:
                    st.error("❌ Erro de encoding. Tente selecionar **Latin-1** ou **Windows-1252**.")
                    st.stop()
                except Exception as e:
                    st.error(f"❌ Erro ao carregar arquivo: {str(e)}")
                    st.stop()

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

            # Mostra qual modelo será usado
            models = llm_client.get_current_models()
            st.caption(f"Modelo: `{models['analysis']}`")

            col_diag1, col_diag2 = st.columns([1, 3])
            with col_diag1:
                diagnose_btn = st.button("🔍 Diagnosticar com IA", type="primary", use_container_width=True)

            if diagnose_btn:
                model_name = models['analysis'].split('/')[-1]
                with st.spinner(f"🤖 {model_name} analisando estrutura dos dados..."):
                    st.session_state.analysis_result = st.session_state.sanitizer.analyze()

            # Mostra resultado da análise
            if st.session_state.analysis_result is not None:
                if st.session_state.analysis_result.success:
                    st.success("✅ Análise concluída!")

                    with st.expander("📊 Ver Diagnóstico Completo", expanded=True):
                        analysis = st.session_state.analysis_result.analysis

                        if isinstance(analysis, dict) and "_parse_error" not in analysis and "error" not in analysis:
                            for col_name, col_info in analysis.items():
                                # Pula chaves internas
                                if col_name.startswith("_"):
                                    continue
                                with st.container():
                                    st.markdown(f"**Coluna: `{col_name}`**")
                                    if isinstance(col_info, dict):
                                        st.markdown(f"- Tipo: `{col_info.get('tipo_identificado', 'N/A')}`")

                                        problemas = col_info.get('problemas', [])
                                        if problemas:
                                            if isinstance(problemas, list):
                                                for p in problemas:
                                                    st.markdown(f"  - {p}")
                                            else:
                                                st.markdown(f"- Problemas: {problemas}")

                                        sugestao = col_info.get('sugestao_limpeza', '')
                                        if sugestao:
                                            st.markdown(f"- Sugestão: _{sugestao}_")
                                    st.markdown("---")
                        else:
                            st.warning("⚠️ A análise retornou dados parciais ou inválidos.")
                            if st.session_state.analysis_result.raw_response:
                                with st.expander("Ver resposta bruta do modelo"):
                                    st.code(st.session_state.analysis_result.raw_response)
                else:
                    error_msg, error_type = format_error_message(st.session_state.analysis_result.error or "Erro desconhecido")
                    if error_type == "warning":
                        st.warning(f"⚠️ {error_msg}")
                    else:
                        st.error(f"❌ {error_msg}")

                    # Mostra resposta bruta se disponível
                    if st.session_state.analysis_result.raw_response:
                        with st.expander("Ver resposta bruta do modelo"):
                            st.code(st.session_state.analysis_result.raw_response)

            # Botão de higienização
            st.header("4️⃣ Higienização dos Dados")

            # Mostra qual modelo será usado
            st.caption(f"Modelo: `{models['sql_gen']}`")

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
                model_name = models['sql_gen'].split('/')[-1]
                with st.spinner(f"🤖 {model_name} gerando SQL de limpeza..."):
                    st.session_state.cleaning_result = st.session_state.sanitizer.clean()

                    if st.session_state.cleaning_result.success:
                        st.session_state.clean_df = st.session_state.cleaning_result.clean_data

            # Mostra resultado da limpeza
            if st.session_state.cleaning_result is not None:
                if st.session_state.cleaning_result.success:
                    success_msg = "✅ Dados higienizados com sucesso!"
                    if st.session_state.cleaning_result.retries > 0:
                        success_msg += f' <span class="retry-badge">🔄 {st.session_state.cleaning_result.retries} correções automáticas</span>'
                    st.markdown(success_msg, unsafe_allow_html=True)

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
                        st.subheader("Raciocínio da IA")
                        st.caption("O processo de pensamento (Chain of Thought) ao gerar o SQL:")
                        reasoning = st.session_state.cleaning_result.reasoning or "Sem raciocínio disponível"
                        st.markdown(reasoning)

                    with tab_logs:
                        st.subheader("Logs de Execução")
                        st.caption("Timeline detalhada do processo de higienização:")
                        render_logs(st.session_state.cleaning_result.logs)

                else:
                    error_msg, error_type = format_error_message(st.session_state.cleaning_result.error)
                    if error_type == "warning":
                        st.warning(f"⚠️ {error_msg}")
                    else:
                        st.error(f"❌ {error_msg}")

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

            # Logs gerais
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

            # Botão de reset no fim da página
            st.markdown("---")
            col_reset_bottom, col_empty2 = st.columns([1, 4])
            with col_reset_bottom:
                if st.button("🔄 Resetar Dados", key="reset_bottom", help="Limpa todos os dados e volta ao estado inicial"):
                    reset_data_state()
                    st.rerun()


if __name__ == "__main__":
    main()
