import json
import os
import io
import random
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
import plotly.express as px
import plotly.graph_objects as go
from xhtml2pdf import pisa
import base64

from ofxparse import OfxParser
import pandas as pd
import plotly.express as px
from supabase import Client, create_client
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Configuração da página
st.set_page_config(
    page_title="Tesouraria Igreja - Controle Financeiro",
    page_icon="📊",
    layout="wide"
)

# --- CONEXÃO COM O SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_supabase()

# --- CONFIGURAÇÕES DE E-MAIL CENTRAL ---
SMTP_SERVER = st.secrets["email"]["smtp_server"]
SMTP_PORT = st.secrets["email"]["smtp_port"]
EMAIL_REMETENTE = st.secrets["email"]["remetente"]
EMAIL_SENHA_APP = st.secrets["email"]["senha_app"]

def enviar_codigo_email(email_destino, codigo):
    msg = MIMEText(
        f"Seu código de segurança para redefinição de senha é: {codigo}\n\n"
        f"Se você não solicitou a alteração, ignore este e-mail."
    )
    msg["Subject"] = "Código de Segurança - Tesouraria"
    msg["From"] = EMAIL_REMETENTE
    msg["To"] = email_destino

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_REMETENTE, EMAIL_SENHA_APP)
        server.sendmail(EMAIL_REMETENTE, email_destino, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Erro ao enviar e-mail: {e}")
        return False

# --- AUTENTICAÇÃO ---
with open("config.yaml") as file:
    config_auth = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config_auth["credentials"],
    config_auth["cookie"]["name"],
    config_auth["cookie"]["key"],
    config_auth["cookie"]["expiry_days"],
)

authenticator.login()

if st.session_state["authentication_status"] is False:
    st.error("Usuário ou senha incorretos.")
    st.stop()
elif st.session_state["authentication_status"] is None:
    st.warning("Por favor, digite seu usuário e senha para acessar.")
    st.stop()

# --- SESSÃO AUTENTICADA ---
usuario_atual = st.session_state["username"]
nome_atual = st.session_state["name"]

authenticator.logout("Sair", "sidebar")
st.sidebar.write(f"Bem-vindo(a), *{nome_atual}*")

# --- BARRA LATERAL: TROCA DE SENHA ---
with st.sidebar.expander("🔑 Alterar Minha Senha"):
    email_user = config_auth["credentials"]["usernames"][usuario_atual].get("email", "")

    if "codigo_gerado" not in st.session_state:
        st.session_state["codigo_gerado"] = None

    if st.button("Enviar Código para meu E-mail"):
        if email_user:
            codigo = str(random.randint(100000, 999999))
            st.session_state["codigo_gerado"] = codigo
            if enviar_codigo_email(email_user, codigo):
                st.success(f"Código enviado para {email_user}")
        else:
            st.error("E-mail não cadastrado para o seu usuário no sistema.")

    codigo_input = st.text_input("Código de 6 dígitos recebido:")
    nova_senha_propria = st.text_input("Nova Senha:", type="password")

    if st.button("Confirmar Nova Senha"):
        if codigo_input and codigo_input == st.session_state.get("codigo_gerado"):
            senha_hash = stauth.Hasher().hash(nova_senha_propria)
            config_auth["credentials"]["usernames"][usuario_atual]["password"] = senha_hash
            with open("config.yaml", "w") as f:
                yaml.dump(config_auth, f, default_flow_style=False)
            st.success("Senha alterada com sucesso!")
            st.session_state["codigo_gerado"] = None
        else:
            st.error("Código de segurança inválido ou não informado.")

# --- PAINEL ADMIN ---
if usuario_atual == "admin":
    st.sidebar.markdown("---")
    st.sidebar.subheader("👑 Painel Admin")

    with st.sidebar.expander("➕ Cadastrar Novo Usuário"):
        novo_nome = st.text_input("Nome Completo")
        novo_user = st.text_input("Login")
        novo_email = st.text_input("E-mail")
        nova_senha = st.text_input("Senha Inicial", type="password")

        if st.button("Salvar Usuário"):
            if novo_user and nova_senha:
                senha_hash = stauth.Hasher().hash(nova_senha)
                config_auth["credentials"]["usernames"][novo_user] = {
                    "email": novo_email,
                    "name": novo_nome,
                    "password": senha_hash,
                }
                with open("config.yaml", "w") as f:
                    yaml.dump(config_auth, f, default_flow_style=False)
                st.success(f"Usuário '{novo_user}' criado!")
                st.rerun()

    with st.sidebar.expander("🔑 Alterar Senha de Usuário"):
        users_lista = list(config_auth["credentials"]["usernames"].keys())
        u_sel = st.selectbox("Selecione o usuário:", users_lista, key="admin_sel_user")
        u_nova_senha = st.text_input("Nova Senha para Usuário:", type="password", key="admin_nova_senha")

        if st.button("Atualizar Senha do Usuário"):
            if u_nova_senha:
                senha_hash = stauth.Hasher().hash(u_nova_senha)
                config_auth["credentials"]["usernames"][u_sel]["password"] = senha_hash
                with open("config.yaml", "w") as f:
                    yaml.dump(config_auth, f, default_flow_style=False)
                st.success(f"Senha de '{u_sel}' atualizada!")
                st.rerun()

    with st.sidebar.expander("🗑️ Excluir Usuário"):
        users_para_del = [u for u in config_auth["credentials"]["usernames"].keys() if u != "admin"]
        if users_para_del:
            u_del = st.selectbox("Selecione para remover:", users_para_del)
            if st.button("Remover Usuário", type="primary"):
                del config_auth["credentials"]["usernames"][u_del]
                with open("config.yaml", "w") as f:
                    yaml.dump(config_auth, f, default_flow_style=False)
                st.success(f"Usuário '{u_del}' removido!")
                st.rerun()

# --- CONFIGURAÇÕES DA IGREJA (JSON LOCAL) ---
CAMINHO_CONFIG = "dados/config.json"
if not os.path.exists("dados"):
    os.makedirs("dados")

def carregar_config():
    if os.path.exists(CAMINHO_CONFIG) and os.path.getsize(CAMINHO_CONFIG) > 0:
        with open(CAMINHO_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        config_padrao = {
            "nome_igreja": "Primeira Igreja Batista Luz do Mundo",
            "tesoureiro": "Elizane Batista Sobrinho",
            "vice_tesoureiro": "Maria Rita de Cassia Da Silva Leão",
            "categorias_entrada": ["Dízimo", "Oferta Geral", "Oferta Missões", "Oferta de Obras/Construção"],
            "categorias_saida": ["Manutenção e Obras", "Energia e Água", "Prebenda Pastoral / Pessoal", "Ação Social", "Material de Escritório / Impressos", "Aluguel / Encargos", "Ministério de Louvor / Música", "Outras Despesas"]
        }
        with open(CAMINHO_CONFIG, "w", encoding="utf-8") as f:
            json.dump(config_padrao, f, ensure_ascii=False, indent=2)
        return config_padrao

# --- GERADOR DE PDF A PARTIR DE TEMPLATES HTML/CSS ---
def gerar_pdf_relatorio_html(nome_igreja, ano_sel, df_fc_matrix, dre_matriz, df_diz_exibir, fig_evolucao=None, fig_dre_pie=None, observacoes_gerais=""):
    def fmt(v):
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    meses_nomes_completos = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                             'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    meses_siglas = list(df_fc_matrix.columns)

    # Totais Globais
    tot_rec = df_fc_matrix.loc['Receitas'].sum()
    tot_desp = df_fc_matrix.loc['Despesas'].sum()
    tot_sld = df_fc_matrix.loc['Saldo'].sum()

    # 1. Linhas Tabela Mês a Mês (Fluxo de Caixa)
    linhas_fc_detalhada = ""
    for idx, sigla in enumerate(meses_siglas):
        m_nome = meses_nomes_completos[idx]
        r = df_fc_matrix.loc['Receitas', sigla]
        d = df_fc_matrix.loc['Despesas', sigla]
        s = df_fc_matrix.loc['Saldo', sigla]
        linhas_fc_detalhada += f"<tr><td>{m_nome}</td><td>{fmt(r)}</td><td>{fmt(d)}</td><td><strong>{fmt(s)}</strong></td></tr>"
    
    # Linha Total Ano
    linhas_fc_detalhada += f"<tr class='total-row'><td>TOTAL DO ANO</td><td>{fmt(tot_rec)}</td><td>{fmt(tot_desp)}</td><td>{fmt(tot_sld)}</td></tr>"

    # 2. Linhas DRE Executivo
    linhas_dre_executivo = f"<tr class='total-row'><td>RECEITAS TOTAIS</td><td style='text-align: right;'>{fmt(tot_rec)}</td></tr>"
    for cat in dre_matriz.index:
        val_cat = dre_matriz.loc[cat, 'Total']
        linhas_dre_executivo += f"<tr><td style='padding-left: 12px;'>• {cat}</td><td style='text-align: right;'>{fmt(val_cat)}</td></tr>"
    
    linhas_dre_executivo += f"<tr class='despesa-row'><td>DESPESAS TOTAIS</td><td style='text-align: right;'>{fmt(tot_desp)}</td></tr>"
    for cat in config.get("categorias_saida", []):
        # Soma a categoria nas despesas se existir na matriz
        val_sai = dre_matriz.loc[cat, 'Total'] if cat in dre_matriz.index else 0.0
        if val_sai > 0:
            linhas_dre_executivo += f"<tr><td style='padding-left: 12px;'>• {cat}</td><td style='text-align: right;'>{fmt(val_sai)}</td></tr>"

    linhas_dre_executivo += f"<tr class='superavit-row'><td>SUPERÁVIT / DÉFICIT LÍQUIDO</td><td style='text-align: right;'>{fmt(tot_sld)}</td></tr>"

    # 3. Linhas Dizimistas Executivo
    linhas_diz_executivo = ""
    for label in ['Dizimistas Identificados', 'Dízimos Anônimos']:
        total_diz = int(df_diz_exibir.loc[label, 'Total Anual'])
        linhas_diz_executivo += f"<tr><td>{label}</td><td style='text-align: right;'><strong>{total_diz}</strong></td></tr>"

    # --- CONVERSÃO DO GRÁFICO PLOTLY ---
    # --- CONVERSÃO DO GRÁFICO USANDO MATPLOTLIB COM LINHA SUAVIZADA E RESPONSIVA ---
    img_evolucao_html = ""
    if df_fc_matrix is not None:
        try:
            import numpy as np
            from scipy.interpolate import make_interp_spline

            fig, ax = plt.subplots(figsize=(7, 2.2), dpi=150)
            meses_siglas_mat = list(df_fc_matrix.columns)
            receitas_vals = df_fc_matrix.loc['Receitas'].values
            despesas_vals = df_fc_matrix.loc['Despesas'].values
            saldo_vals = df_fc_matrix.loc['Saldo'].values

            x = np.arange(len(meses_siglas_mat))
            width = 0.35

            # Desenha as barras de Receitas e Despesas
            ax.bar(x - width/2, receitas_vals, width, label='Receitas', color='#2ecc71')
            ax.bar(x + width/2, despesas_vals, width, label='Despesas', color='#e74c3c')

            # Linha de Saldo Suavizada (Spline)
            if len(x) > 3 and np.max(np.abs(saldo_vals)) > 0:
                try:
                    X_spline = np.linspace(x.min(), x.max(), 300)
                    spl = make_interp_spline(x, saldo_vals, k=3)
                    Y_spline = spl(X_spline)
                    ax.plot(X_spline, Y_spline, color='#3498db', linewidth=2.5, label='Saldo')
                except Exception:
                    ax.plot(x, saldo_vals, color='#3498db', marker='o', linewidth=2, label='Saldo')
            else:
                ax.plot(x, saldo_vals, color='#3498db', marker='o', linewidth=2, label='Saldo')

            ax.set_xticks(x)
            ax.set_xticklabels(meses_siglas_mat, fontsize=8)
            ax.legend(loc='upper center', bbox_to_anchor=(0.5, 1.25), ncol=3, fontsize=8, frameon=False)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.grid(True, linestyle='--', alpha=0.3)
            plt.tight_layout()

            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', bbox_inches='tight', transparent=True)
            buffer.seek(0)
            b64_str = base64.b64encode(buffer.read()).decode('utf-8')
            plt.close(fig)

            # Tag HTML fluida e responsiva para computadores e telemóveis
            img_evolucao_html = f'<div style="text-align: center; margin-bottom: 8px;"><img src="data:image/png;base64,{b64_str}" width="550" height="130" style="width: 550px; height: 130px;" /></div>'
        except Exception as e:
            img_evolucao_html = f"<!-- Erro Matplotlib PDF: {e} -->"

    # Leitura dos arquivos de template
    caminho_css = os.path.join("templates", "relatorio.css")
    caminho_html = os.path.join("templates", "relatorio.html")

    with open(caminho_css, "r", encoding="utf-8") as f_css:
        estilo_css = f_css.read()

    with open(caminho_html, "r", encoding="utf-8") as f_html:
        template_html = f_html.read()

    # Preenchimento do template HTML
    html_final = template_html.format(
        estilo_css=estilo_css,
        nome_igreja=nome_igreja,
        ano_sel=ano_sel,
        total_receitas=fmt(tot_rec),
        total_despesas=fmt(tot_desp),
        total_saldo=fmt(tot_sld),
        img_evolucao_html=img_evolucao_html,
        linhas_fc_detalhada=linhas_fc_detalhada,
        linhas_dre_executivo=linhas_dre_executivo,
        linhas_diz_executivo=linhas_diz_executivo,
        observacoes_gerais=observacoes_gerais if observacoes_gerais else "Nenhuma observação registrada para este exercício.",
        data_geracao=datetime.now().strftime('%d/%m/%Y às %H:%M')
    )

    pdf_buffer = io.BytesIO()
    pisa.CreatePDF(io.StringIO(html_final), dest=pdf_buffer)
    return pdf_buffer.getvalue()

# --- FUNÇÕES DE BANCO DE DADOS (SUPABASE) ---
@st.cache_data(ttl=600)
def carregar_dados():
    try:
        response = supabase.table("lancamentos").select("*").execute()
        data = response.data
        if data:
            df = pd.DataFrame(data)
            df['data'] = pd.to_datetime(df['data'])
            return df
        else:
            return pd.DataFrame(columns=[
                'id', 'data', 'mes_referencia', 'origem', 'tipo_movimento', 
                'categoria', 'descricao', 'valor', 'qtd_dizimistas', 'id_dizimista'
            ])
    except Exception as e:
        st.error(f"Erro ao carregar dados do Supabase: {e}")
        return pd.DataFrame(columns=[
            'id', 'data', 'mes_referencia', 'origem', 'tipo_movimento', 
            'categoria', 'descricao', 'valor', 'qtd_dizimistas', 'id_dizimista'
        ])

def salvar_dados(novos_dados):
    try:
        dados_tratados = []
        for item in novos_dados:
            item_limpo = dict(item)
            
            # 1. Se o 'id' for gerado automaticamente pelo Supabase (int8), 
            # removemos do envio para não dar conflito de tipo.
            item_limpo.pop('id', None)
            item_limpo.pop('created_at', None)

            # 2. Trata campo de data (YYYY-MM-DD)
            if isinstance(item_limpo.get('data'), (datetime, pd.Timestamp)):
                item_limpo['data'] = item_limpo['data'].strftime('%Y-%m-%d')
            else:
                item_limpo['data'] = str(item_limpo['data'])

            # 3. Garante valores padrão para campos obrigatórios de texto
            item_limpo['mes_referencia'] = str(item_limpo.get('mes_referencia', ''))
            item_limpo['origem'] = str(item_limpo.get('origem', ''))
            item_limpo['tipo_movimento'] = str(item_limpo.get('tipo_movimento', ''))
            item_limpo['categoria'] = str(item_limpo.get('categoria', ''))
            item_limpo['descricao'] = str(item_limpo.get('descricao', ''))

            # 4. Garante tipos numéricos compatíveis (numeric, int4, int8)
            item_limpo['valor'] = float(item_limpo.get('valor', 0.0))
            item_limpo['qtd_dizimistas'] = int(item_limpo.get('qtd_dizimistas', 0))
            item_limpo['id_dizimista'] = int(item_limpo.get('id_dizimista', 0))

            dados_tratados.append(item_limpo)
        
        # Inserção no Supabase fora do loop
        resposta = supabase.table("lancamentos").insert(dados_tratados).execute()
        
        # Limpa o cache para recarregar a tabela na interface do Streamlit
        st.cache_data.clear()
        return True

    except Exception as e:
        st.error(f"Erro ao salvar lançamento no Supabase: {e}")
        return False

def atualizar_lancamento(id_lancamento, dados_atualizados):
    try:
        if isinstance(dados_atualizados.get("data"), (datetime, pd.Timestamp)):
            dados_atualizados["data"] = dados_atualizados["data"].strftime("%Y-%m-%d")
        else:
            dados_atualizados["data"] = str(dados_atualizados["data"])
            
        supabase.table("lancamentos").update(dados_atualizados).eq("id", id_lancamento).execute()
    except Exception as e:
        st.error(f"Erro ao atualizar lançamento: {e}")

def deletar_lancamento(id_lancamento):
    try:
        supabase.table("lancamentos").delete().eq("id", id_lancamento).execute()
    except Exception as e:
        st.error(f"Erro ao deletar lançamento: {e}")

def carregar_dizimistas():
    try:
        response = supabase.table("dizimistas").select("*").execute()
        data = response.data
        if data:
            return pd.DataFrame(data)
        else:
            return pd.DataFrame(columns=['id_dizimista', 'nome', 'telefone'])
    except Exception as e:
        st.error(f"Erro ao carregar dizimistas do Supabase: {e}")
        return pd.DataFrame(columns=['id_dizimista', 'nome', 'telefone'])

def salvar_dizimista(nome, telefone):
    try:
        novo_registro = {"nome": nome, "telefone": telefone}
        supabase.table("dizimistas").insert(novo_registro).execute()
    except Exception as e:
        st.error(f"Erro ao salvar dizimista no Supabase: {e}")

def atualizar_dizimista(id_dizimista, nome, telefone):
    try:
        supabase.table("dizimistas").update({"nome": nome, "telefone": telefone}).eq("id_dizimista", id_dizimista).execute()
    except Exception as e:
        st.error(f"Erro ao atualizar dizimista: {e}")

def deletar_dizimista(id_dizimista):
    try:
        supabase.table("dizimistas").delete().eq("id_dizimista", id_dizimista).execute()
    except Exception as e:
        st.error(f"Erro ao deletar dizimista: {e}")

def extrair_dados_ofx(arquivo_ofx):
    ofx = OfxParser.parse(arquivo_ofx)
    transacoes = ofx.account.statement.transactions
    registros = []
    for t in transacoes:
        desc = t.memo if t.memo else (t.payee if t.payee else "Transação Bancária")
        registros.append({
            'data': t.date.date(),
            'descricao': desc,
            'valor': float(abs(t.amount)),
            'tipo_movimento': "Entrada" if t.amount > 0 else "Saída"
        })
    return pd.DataFrame(registros)

def carregar_anotacoes(ano, mes):
    try:
        response = supabase.table("anotacoes_mes").select("observacoes").eq("ano", ano).eq("mes", mes).execute()
        if response.data:
            return response.data[0].get("observacoes", "")
        return ""
    except Exception:
        return ""

def salvar_anotacao(ano, mes, texto):
    try:
        supabase.table("anotacoes_mes").upsert(
            {"ano": ano, "mes": mes, "observacoes": texto},
            on_conflict="ano,mes"
        ).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar observação: {e}")
        return False

# Carregar dados iniciais
config = carregar_config()
df_base = carregar_dados()
df_dizimistas = carregar_dizimistas()

# Dicionário auxiliar para selectbox de dizimistas
opcoes_dizimistas = {0: "Anônimo / Não Identificado"}
if not df_dizimistas.empty:
    for _, row in df_dizimistas.iterrows():
        opcoes_dizimistas[int(row['id_dizimista'])] = f"{row['nome']} (ID: {int(row['id_dizimista'])})"

st.title(f"📊 Tesouraria — {config['nome_igreja']}")

# --- MENU LATERAL DE NAVEGAÇÃO ---
opcao_sidebar = st.sidebar.radio("Navegação", [
    "Visualizar Dashboards", 
    "Lançar Espécie (Culto)", 
    "Importar Extrato OFX",
    "Editar / Excluir Lançamentos",
    "Cadastrar / Editar Dizimistas",
    "Anotações / Observações do Mês",
    "Configurações (JSON)"
])

# 1. CADASTRAR / EDITAR DIZIMISTAS
if opcao_sidebar == "Cadastrar / Editar Dizimistas":
    st.header("👤 Gestão de Dizimistas")
    aba_cad, aba_edit_diz = st.tabs(["Cadastrar Novo", "Editar / Excluir Existente"])

    with aba_cad:
        with st.form("form_cad_dizimista", clear_on_submit=True):
            nome_diz = st.text_input("Nome Completo do Membro")
            tel_diz = st.text_input("Telefone / WhatsApp (Opcional)")
            
            if st.form_submit_button("Salvar Dizimista"):
                if nome_diz.strip():
                    salvar_dizimista(nome_diz.strip(), tel_diz.strip())
                    st.success(f"Dizimista '{nome_diz}' cadastrado com sucesso!")
                    st.rerun()
                else:
                    st.warning("O nome não pode ficar em branco.")
        
        st.subheader("Membros Cadastrados")
        st.dataframe(df_dizimistas, use_container_width=True)

    with aba_edit_diz:
        if df_dizimistas.empty:
            st.info("Nenhum dizimista cadastrado para editar.")
        else:
            id_sel_edit = st.selectbox(
                "Selecione o Dizimista para Alterar", 
                options=df_dizimistas['id_dizimista'].tolist(),
                format_func=lambda x: f"{df_dizimistas[df_dizimistas['id_dizimista'] == x]['nome'].values[0]} (ID: {x})"
            )
            
            diz_atual = df_dizimistas[df_dizimistas['id_dizimista'] == id_sel_edit].iloc[0]

            with st.form("form_editar_dizimista"):
                novo_nome = st.text_input("Nome", value=diz_atual['nome'])
                novo_tel = st.text_input("Telefone", value=str(diz_atual['telefone']) if pd.notna(diz_atual['telefone']) else "")
                
                col_b1, col_b2 = st.columns(2)
                btn_atualizar = col_b1.form_submit_button("Atualizar Dados")
                btn_deletar = col_b2.form_submit_button("Excluir Cadastro")

                if btn_atualizar:
                    atualizar_dizimista(id_sel_edit, novo_nome.strip(), novo_tel.strip())
                    st.success("Cadastro atualizado com sucesso!")
                    st.rerun()

                if btn_deletar:
                    deletar_dizimista(id_sel_edit)
                    st.warning("Dizimista excluído com sucesso!")
                    st.rerun()

# 2. LANÇAMENTO EM ESPÉCIE ( ENTRADAS E SAÍDAS )
elif opcao_sidebar == "Lançar Espécie (Culto)":
    st.header("💵 Lançamento em Espécie (Caixa do Culto)")
    
    aba_ent, aba_sai = st.tabs(["📥 Registrar Entradas (Receitas)", "📤 Registrar Saídas (Despesas)"])

    with aba_ent:
        with st.form("form_especie_entrada", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            data_culto = c1.date_input("Data do Culto", datetime.now(), key="ent_data")
            mes_ref = c2.text_input("Mês de Competência (YYYY-MM)", value=datetime.now().strftime("%Y-%m"), key="ent_mes")
            turno = c3.selectbox("Evento / Turno", ["Domingo Noite", "Domingo Manhã", "Culto de Ensino", "Eventos / Outros"], key="ent_turno")
            
            st.subheader("Valores de Entradas Contados")
            
            # Dízimos Separados
            v_dizimos = st.number_input("Total em Dízimos (Espécie)", min_value=0.0, step=10.0, format="%.2f")
            id_diz_sel = st.selectbox("Vincular a Dizimista Específico (Opcional)", 
                                      options=list(opcoes_dizimistas.keys()), 
                                      format_func=lambda x: opcoes_dizimistas[x])
            
            # Outras Entradas baseadas no JSON de configuração
            outros_valores = {}
            cats_ent_config = [c for c in config.get("categorias_entrada", []) if c != "Dízimo"]
            
            st.markdown("---")
            st.markdown("**Outras Categorias de Entrada:**")
            for cat in cats_ent_config:
                outros_valores[cat] = st.number_input(f"Total em {cat}", min_value=0.0, step=10.0, format="%.2f", key=f"cat_ent_{cat}")

            responsaveis_ent = st.text_input("Responsáveis pela Contagem", value=config['tesoureiro'], key="ent_resp")
            
            if st.form_submit_button("Gravar Entradas em Espécie"):
                novos_registros = []
                agora_str = datetime.now().strftime("%Y%m%d%H%M%S")
                contador = 1

                # Salva Dízimo separadamente se houver valor
                if v_dizimos > 0:
                    novos_registros.append({
                        'id': f"ESP-ENT-{agora_str}-{contador}", 'data': data_culto, 'mes_referencia': mes_ref,
                        'origem': 'Espécie', 'tipo_movimento': 'Entrada', 'categoria': 'Dízimo',
                        'descricao': f"Dízimos em espécie - {turno} (Resp: {responsaveis_ent})",
                        'valor': v_dizimos, 'qtd_dizimistas': 1 if id_diz_sel != 0 else 0,
                        'id_dizimista': id_diz_sel
                    })
                    contador += 1

                # Salva as demais categorias de entrada individualmente
                for cat, val in outros_valores.items():
                    if val > 0:
                        novos_registros.append({
                            'id': f"ESP-ENT-{agora_str}-{contador}", 'data': data_culto, 'mes_referencia': mes_ref,
                            'origem': 'Espécie', 'tipo_movimento': 'Entrada', 'categoria': cat,
                            'descricao': f"{cat} em espécie - {turno}", 'valor': val, 
                            'qtd_dizimistas': 0, 'id_dizimista': 0
                        })
                        contador += 1

                if novos_registros:
                    salvar_dados(novos_registros)
                    st.success("Entradas registradas com sucesso!")
                    st.rerun()
                else:
                    st.warning("Insira ao menos um valor maior que zero para gravar.")

    with aba_sai:
        with st.form("form_especie_saida", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            data_saida = c1.date_input("Data da Saída", datetime.now(), key="sai_data")
            mes_ref_sai = c2.text_input("Mês de Competência (YYYY-MM)", value=datetime.now().strftime("%Y-%m"), key="sai_mes")
            cat_saida = c3.selectbox("Categoria da Despesa", options=config.get("categorias_saida", ["Outras Despesas"]), key="sai_cat")

            v_saida = st.number_input("Valor da Saída / Despesa (R$)", min_value=0.0, step=10.0, format="%.2f", key="sai_val")
            desc_saida = st.text_input("Descrição / Histórico / Favorecido", key="sai_desc")
            resp_saida = st.text_input("Responsável pelo Pagamento", value=config['tesoureiro'], key="sai_resp")

            if st.form_submit_button("Gravar Saída em Espécie"):
                if v_saida > 0 and desc_saida.strip():
                    agora_str = datetime.now().strftime("%Y%m%d%H%M%S")
                    registro_saida = [{
                        'id': f"ESP-SAI-{agora_str}-1",
                        'data': data_saida,
                        'mes_referencia': mes_ref_sai,
                        'origem': 'Espécie',
                        'tipo_movimento': 'Saída',
                        'categoria': cat_saida,
                        'descricao': f"{desc_saida} (Resp: {resp_saida})",
                        'valor': v_saida,
                        'qtd_dizimistas': 0,
                        'id_dizimista': 0
                    }]
                    salvar_dados(registro_saida)
                    st.success("Saída registrada com sucesso!")
                    st.rerun()
                else:
                    st.warning("Informe um valor maior que zero e preencha a descrição da despesa.")

# 3. IMPORTAR EXTRATO OFX
elif opcao_sidebar == "Importar Extrato OFX":
    st.header("Importação de Extrato Bancário (.ofx)")
    col_i1, col_i2 = st.columns(2)
    mes_referencia_upload = col_i1.text_input("Mês de Competência (YYYY-MM)", value=datetime.now().strftime("%Y-%m"))
    arquivo_ofx = col_i2.file_uploader("Selecione o arquivo .OFX fornecido pelo banco", type=["ofx"])

    if arquivo_ofx is not None:
        try:
            df_ofx = extrair_dados_ofx(arquivo_ofx)
            st.dataframe(df_ofx)

            with st.form("form_conciliacao_ofx"):
                dados_conciliados = []
                categorias_todas = config["categorias_entrada"] + config["categorias_saida"]

                for idx, row in df_ofx.iterrows():
                    st.markdown(f"**Item {idx+1}:** {row['descricao']} — **R$ {row['valor']:,.2f}** ({row['tipo_movimento']})")
                    c1, c2, c3, c4 = st.columns(4)
                    
                    data_tx = c1.date_input(f"Data #{idx}", row['data'], key=f"data_{idx}")
                    tipo_mov = c2.selectbox(f"Tipo #{idx}", ["Entrada", "Saída"], index=0 if row['tipo_movimento'] == 'Entrada' else 1, key=f"tipo_{idx}")
                    cat = c3.selectbox(f"Categoria #{idx}", categorias_todas, key=f"cat_{idx}")
                    
                    id_diz = 0
                    if cat == "Dízimo":
                        id_diz = c4.selectbox(f"Dizimista #{idx}", options=list(opcoes_dizimistas.keys()), format_func=lambda x: opcoes_dizimistas[x], key=f"diz_{idx}")

                    dados_conciliados.append({
                        'id': f"BNK-{datetime.now().strftime('%Y%m%d%H%M%S')}-{idx}",
                        'data': data_tx,
                        'mes_referencia': mes_referencia_upload,
                        'origem': 'Banco (OFX)',
                        'tipo_movimento': tipo_mov,
                        'categoria': cat,
                        'descricao': row['descricao'],
                        'valor': row['valor'],
                        'qtd_dizimistas': 1 if id_diz != 0 else 0,
                        'id_dizimista': id_diz
                    })
                    st.divider()

                if st.form_submit_button(f"Confirmar Extrato {mes_referencia_upload}"):
                    salvar_dados(dados_conciliados)
                    st.success("Extrato OFX importado com sucesso!")
                    st.rerun()

        except Exception as e:
            st.error(f"Erro ao processar OFX: {e}")

# 4. EDITAR / EXCLUIR LANÇAMENTOS
elif opcao_sidebar == "Editar / Excluir Lançamentos":
    st.header("✏️ Editar ou Excluir Lançamentos Financeiros")
    
    if df_base.empty:
        st.info("Nenhum lançamento registrado na base.")
    else:
        if 'id_dizimista' not in df_base.columns:
            df_base['id_dizimista'] = 0

        meses_disp = ["Todos"] + sorted(df_base['mes_referencia'].astype(str).unique().tolist())
        mes_filtro = st.selectbox("Filtrar por Mês para Editar", meses_disp)

        df_para_editar = df_base if mes_filtro == "Todos" else df_base[df_base['mes_referencia'] == mes_filtro]

        if df_para_editar.empty:
            st.warning("Nenhum lançamento para este mês.")
        else:
            id_selecionado = st.selectbox(
                "Selecione o Lançamento pelo ID", 
                options=df_para_editar['id'].tolist(),
                format_func=lambda x: f"ID: {x} | {df_para_editar[df_para_editar['id'] == x]['descricao'].values[0]} | R$ {df_para_editar[df_para_editar['id'] == x]['valor'].values[0]:,.2f}"
            )

            linha_sel = df_base[df_base['id'] == id_selecionado].iloc[0]
            categorias_todas = config["categorias_entrada"] + config["categorias_saida"]

            with st.form("form_edicao_lancamento"):
                st.subheader(f"Editando Registro ID: {id_selecionado}")
                col1, col2, col3 = st.columns(3)
                
                dt_edit = col1.date_input("Data", pd.to_datetime(linha_sel['data']))
                mes_ref_edit = col2.text_input("Mês de Referência (YYYY-MM)", value=str(linha_sel['mes_referencia']))
                origem_edit = col3.selectbox("Origem", ["Espécie", "Banco (OFX)"], index=0 if linha_sel['origem'] == "Espécie" else 1)

                col4, col5, col6 = st.columns(3)
                tipo_edit = col4.selectbox("Tipo Movimento", ["Entrada", "Saída"], index=0 if linha_sel['tipo_movimento'] == "Entrada" else 1)
                
                idx_cat = categorias_todas.index(linha_sel['categoria']) if linha_sel['categoria'] in categorias_todas else 0
                cat_edit = col5.selectbox("Categoria", categorias_todas, index=idx_cat)
                val_edit = col6.number_input("Valor (R$)", value=float(linha_sel['valor']), min_value=0.0, step=10.0, format="%.2f")

                desc_edit = st.text_input("Descrição", value=str(linha_sel['descricao']))
                
                diz_id_atual = 0
                if 'id_dizimista' in linha_sel and pd.notna(linha_sel['id_dizimista']):
                    try:
                        diz_id_atual = int(linha_sel['id_dizimista'])
                    except ValueError:
                        diz_id_atual = 0

                keys_diz = list(opcoes_dizimistas.keys())
                idx_diz = keys_diz.index(diz_id_atual) if diz_id_atual in keys_diz else 0
                
                diz_edit = st.selectbox("Dizimista Vinculado", options=keys_diz, index=idx_diz, format_func=lambda x: opcoes_dizimistas[x])

                btn_salvar_edicao = st.form_submit_button("💾 Salvar Alterações no Registro")

                if btn_salvar_edicao:
                    dados_upd = {
                        'data': dt_edit,
                        'mes_referencia': mes_ref_edit,
                        'origem': origem_edit,
                        'tipo_movimento': tipo_edit,
                        'categoria': cat_edit,
                        'valor': val_edit,
                        'descricao': desc_edit,
                        'id_dizimista': diz_edit,
                        'qtd_dizimistas': 1 if diz_edit != 0 else 0
                    }
                    atualizar_lancamento(id_selecionado, dados_upd)
                    st.success("Lançamento atualizado com sucesso!")
                    st.rerun()

            st.divider()
            if st.button("🗑 Excluir Este Lançamento (Ação Irreversível)", type="secondary"):
                deletar_lancamento(id_selecionado)
                st.warning("Lançamento removido com sucesso!")
                st.rerun()

# ANOTAÇÕES E OBSERVAÇÕES DO MÊS

elif opcao_sidebar == "Anotações / Observações do Mês":
    st.header("📝 Anotações e Eventualidades Mensais")
    st.info("Registre fatos relevantes, justificativas ou ocorrências financeiras de cada mês para compor o relatório oficial.")

    col_a1, col_a2 = st.columns(2)
    anos_disp_anot = sorted(df_base['data'].dt.year.unique().tolist()) if not df_base.empty else [datetime.now().year]
    ano_anot = col_a1.selectbox("Ano de Referência:", anos_disp_anot, key="sel_ano_anot")
    
    meses_nomes_lista = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                         'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    mes_anot_nome = col_a2.selectbox("Mês:", meses_nomes_lista, index=datetime.now().month - 1, key="sel_mes_anot")
    mes_anot_num = meses_nomes_lista.index(mes_anot_nome) + 1

    texto_atual = carregar_anotacoes(ano_anot, mes_anot_num)

    with st.form("form_anotacao_mes"):
        st.markdown(f"**Observações para {mes_anot_nome} de {ano_anot}:**")
        obs_input = st.text_area("Descreva aqui eventos extraordinários, reformas, ausências ou observações da tesouraria:", value=texto_atual, height=150)
        
        if st.form_submit_button("Salvar Anotações do Mês"):
            if salvar_anotacao(ano_anot, mes_anot_num, obs_input.strip()):
                st.success(f"Anotações de {mes_anot_nome}/{ano_anot} salvas com sucesso!")
                st.rerun()

# 5. CONFIGURAÇÕES DA IGREJA (JSON)
elif opcao_sidebar == "Configurações (JSON)":
    st.header("⚙️ Configurações Gerais do Sistema")
    st.info("Esses parâmetros ficam salvos no arquivo `dados/config.json`.")

    with st.form("form_config"):
        nome_igreja = st.text_input("Nome da Igreja", value=config.get("nome_igreja", ""))
        tesoureiro = st.text_input("Nome do Tesoureiro Responsável", value=config.get("tesoureiro", ""))
        
        cats_ent = st.text_area("Categorias de Entrada (uma por linha)", value="\n".join(config.get("categorias_entrada", [])))
        cats_sai = st.text_area("Categorias de Saída (uma por linha)", value="\n".join(config.get("categorias_saida", [])))

        if st.form_submit_button("Salvar Configurações"):
            novas_config = {
                "nome_igreja": nome_igreja.strip(),
                "tesoureiro": tesoureiro.strip(),
                "categorias_entrada": [c.strip() for c in cats_ent.split("\n") if c.strip()],
                "categorias_saida": [c.strip() for c in cats_sai.split("\n") if c.strip()]
            }
            with open(CAMINHO_CONFIG, "w", encoding="utf-8") as f:
                json.dump(novas_config, f, ensure_ascii=False, indent=2)
            st.success("Configurações atualizadas com sucesso!")
            st.rerun()

# 6. DASHBOARDS E RELATÓRIOS
elif opcao_sidebar == "Visualizar Dashboards":
    st.header("📊 Dashboard & Relatório de Impressão")

    if df_base.empty:
        st.info("Nenhum registro cadastrado na base.")
    else:
        # Função auxiliar de formatação de moeda R$
        def formatar_moeda(val):
            if pd.isna(val):
                return "R$ 0,00"
            return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        df_temp = df_base.copy()
        df_temp['tipo_movimento'] = df_temp['tipo_movimento'].replace({'Entrada': 'Receita', 'Saída': 'Despesa'})
        df_temp['data'] = pd.to_datetime(df_temp['data'])
        df_temp['mes_ano'] = df_temp['data'].dt.strftime('%Y-%m')

        # Seletor do Mês Ativo e Ano
        anos_disponiveis = sorted(df_temp['data'].dt.year.unique(), reverse=True)
        col_f1, col_f2 = st.columns(2)
        ano_sel = col_f1.selectbox("Ano de Exercício:", anos_disponiveis)
        
        meses_nomes = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                       'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        mes_sel_nome = col_f2.selectbox("Mês de Análise Individual:", meses_nomes, index=datetime.now().month - 1)
        mes_sel_num = meses_nomes.index(mes_sel_nome) + 1

        df_ano = df_temp[df_temp['data'].dt.year == ano_sel].copy()
        df_mes = df_ano[df_ano['data'].dt.month == mes_sel_num].copy()

        # ==============================================================================
        # VISÃO 1: DASHBOARD MENSAL
        # ==============================================================================
        st.markdown(f"### 📅 Análise Mensal — {mes_sel_nome} / {ano_sel}")
        
        rec_mes = df_mes[df_mes['tipo_movimento'] == 'Receita']['valor'].sum()
        desp_mes = df_mes[df_mes['tipo_movimento'] == 'Despesa']['valor'].sum()
        saldo_mes = rec_mes - desp_mes
        lucr_mes = (saldo_mes / rec_mes * 100) if rec_mes > 0 else 0.0

        df_diz_mes = df_mes[df_mes['categoria'].str.contains('Dízimo|Dizimo', case=False, na=False)]
        esp_mes = df_diz_mes[df_diz_mes['id_dizimista'] > 0]['id_dizimista'].nunique()
        anon_mes = df_diz_mes[df_diz_mes['id_dizimista'] == 0]['qtd_dizimistas'].sum()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Receitas", formatar_moeda(rec_mes))
        k2.metric("Despesas", formatar_moeda(desp_mes))
        k3.metric("Saldo do Mês", formatar_moeda(saldo_mes))
        k4.metric("Lucratividade", f"{lucr_mes:.1f}%")

        kd1, kd2, kd3 = st.columns(3)
        kd1.metric("Dizimistas Identificados", esp_mes)
        kd2.metric("Dízimos Anônimos (Envelopes)", int(anon_mes))
        kd3.metric("Total Dizimistas", int(esp_mes + anon_mes))

        st.markdown("---")

        # ==============================================================================
        # VISÃO 2: RELATÓRIO DE IMPRESSÃO (ESTILO PLANILHA EXCEL)
        # ==============================================================================
        st.markdown("## 🖨️ RELATÓRIO DE IMPRESSÃO - FLUXO DE CAIXA")
        st.markdown(f"**{config['nome_igreja']}** | Exercício: **{ano_sel}**")
        st.caption("1. Fluxo de Caixa | 2. DRE (Demonstrativo de Resultado) | 3. Resumo de Dizimistas")

        # Montagem das Matrizes de 12 Meses
        meses_siglas = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
        
        dados_fc = {sigla: {'Receitas': 0.0, 'Despesas': 0.0, 'Saldo': 0.0, 'Diz_Esp': 0, 'Diz_Anon': 0} for sigla in meses_siglas}

        for m in range(1, 13):
            sigla = meses_siglas[m - 1]
            df_m = df_ano[df_ano['data'].dt.month == m]
            
            r_m = df_m[df_m['tipo_movimento'] == 'Receita']['valor'].sum()
            d_m = df_m[df_m['tipo_movimento'] == 'Despesa']['valor'].sum()
            
            df_diz = df_m[df_m['categoria'].str.contains('Dízimo|Dizimo', case=False, na=False)]
            e_m = df_diz[df_diz['id_dizimista'] > 0]['id_dizimista'].nunique()
            a_m = df_diz[df_diz['id_dizimista'] == 0]['qtd_dizimistas'].sum()

            dados_fc[sigla]['Receitas'] = r_m
            dados_fc[sigla]['Despesas'] = d_m
            dados_fc[sigla]['Saldo'] = r_m - d_m
            dados_fc[sigla]['Diz_Esp'] = e_m
            dados_fc[sigla]['Diz_Anon'] = int(a_m)

        df_fc_matrix = pd.DataFrame(dados_fc)

        
        # 1. Gráfico Combinado: Barras (Receitas/Despesas) e Linha Suavizada (Saldo)
        st.subheader("1. Fluxo de Caixa (Evolução Anual)")
        df_chart_anual = pd.DataFrame({
            'Mês': meses_siglas,
            'Receitas': [dados_fc[m]['Receitas'] for m in meses_siglas],
            'Despesas': [dados_fc[m]['Despesas'] for m in meses_siglas],
            'Saldo': [dados_fc[m]['Saldo'] for m in meses_siglas]
        })
        
        fig_evolucao = go.Figure()

        # Adiciona barras para Receitas
        fig_evolucao.add_trace(go.Bar(
            x=df_chart_anual['Mês'], 
            y=df_chart_anual['Receitas'], 
            name='Receitas', 
            marker_color='#2ecc71'
        ))

        # Adiciona barras para Despesas
        fig_evolucao.add_trace(go.Bar(
            x=df_chart_anual['Mês'], 
            y=df_chart_anual['Despesas'], 
            name='Despesas', 
            marker_color='#e74c3c'
        ))

        # Adiciona linha suavizada para o Saldo (com spline)
        fig_evolucao.add_trace(go.Scatter(
            x=df_chart_anual['Mês'], 
            y=df_chart_anual['Saldo'], 
            name='Saldo', 
            mode='lines+markers',
            line=dict(shape='spline', color='#3498db', width=3),
            marker=dict(size=6)
        ))

        # Configuração do layout limpo e legenda horizontal no topo
        fig_evolucao.update_layout(
            barmode='group',
            height=220, 
            margin=dict(l=30, r=20, t=35, b=10),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.05,
                xanchor="center",
                x=0.5,
                title=None
            ),
            xaxis_title=None,
            yaxis_title=None,
            plot_bgcolor='rgba(0,0,0,0)',  # Fundo interno transparente
            paper_bgcolor='rgba(0,0,0,0)', # Fundo externo transparente
            xaxis=dict(
                showgrid=True, 
                gridcolor='rgba(128, 128, 128, 0.2)' # Grelha subtil adaptável
            ),
            yaxis=dict(
                showgrid=True, 
                gridcolor='rgba(128, 128, 128, 0.2)'
            )
        )
        # Desenha o gráfico combinado na interface do Streamlit
        st.plotly_chart(fig_evolucao, use_container_width=True)

        # Tabela 1: Fluxo de Caixa Matriz (12 Meses + Total)
        df_fc_exibir = df_fc_matrix.loc[['Receitas', 'Despesas', 'Saldo']].copy()
        df_fc_exibir['Total Anual'] = df_fc_exibir.sum(axis=1)

        st.dataframe(
            df_fc_exibir.style.format(formatar_moeda),
            use_container_width=True
        )

        # 2. DRE e Gráfico de Rosca
        st.subheader("2. DRE (Demonstrativo de Resultado do Exercício)")
        c_dre1, c_dre2 = st.columns([1, 2])
        
        with c_dre1:
            df_pie_dre = df_ano[df_ano['tipo_movimento'] == 'Receita'].groupby('categoria')['valor'].sum().reset_index()
            if not df_pie_dre.empty:
                fig_dre_pie = px.pie(df_pie_dre, values='valor', names='categoria', hole=0.5)
                fig_dre_pie.update_layout(showlegend=False, height=250, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_dre_pie, use_container_width=True)

        with c_dre2:
            dre_matriz = df_ano.pivot_table(index='categoria', columns=df_ano['data'].dt.month, values='valor', aggfunc='sum', fill_value=0)
            dre_matriz.columns = [meses_siglas[m - 1] for m in dre_matriz.columns]
            for col_missing in set(meses_siglas) - set(dre_matriz.columns):
                dre_matriz[col_missing] = 0.0
            dre_matriz = dre_matriz[meses_siglas]
            dre_matriz['Total'] = dre_matriz.sum(axis=1)

            st.dataframe(
                dre_matriz.style.format(formatar_moeda),
                use_container_width=True
            )

        # 3. Resumo de Dizimistas
        st.subheader("3. Estatísticas de Dizimistas (Mês a Mês)")
        df_diz_exibir = df_fc_matrix.loc[['Diz_Esp', 'Diz_Anon']].copy()
        df_diz_exibir.index = ['Dizimistas Identificados', 'Dízimos Anônimos']
        df_diz_exibir['Total Anual'] = df_diz_exibir.sum(axis=1)

        st.dataframe(df_diz_exibir, use_container_width=True)

        # Buscar anotações do ano para consolidar no relatório
        observacoes_texto = ""
        try:
            resp_anot = supabase.table("anotacoes_mes").select("mes, observacoes").eq("ano", ano_sel).order("mes").execute()
            if resp_anot.data:
                linhas_obs = []
                for row in resp_anot.data:
                    m_nome = meses_nomes[row['mes'] - 1]
                    if row['observacoes']:
                        linhas_obs.append(f"<b>{m_nome}:</b> {row['observacoes']}")
                observacoes_texto = "<br>".join(linhas_obs)
        except Exception:
            observacoes_texto = "Nenhuma observação registrada para este exercício."

        if not observacoes_texto:
            observacoes_texto = "Nenhuma observação registrada para este exercício."

        # Gerar o arquivo PDF passando as observações
        pdf_bytes = gerar_pdf_relatorio_html(
            config['nome_igreja'], 
            ano_sel, 
            df_fc_matrix, 
            dre_matriz, 
            df_diz_exibir,
            fig_evolucao=fig_evolucao, # <--- Garanta que esta linha está incluída
            fig_dre_pie=fig_dre_pie,
            observacoes_gerais=observacoes_texto
        )

        st.markdown("---")
        st.download_button(
            label="📄 Baixar Relatório Completo em PDF",
            data=pdf_bytes,
            file_name=f"relatorio_financeiro_{ano_sel}.pdf",
            mime="application/pdf",
            type="primary"
        )