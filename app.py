import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os
import json
from ofxparse import OfxParser

# Configuração da página
st.set_page_config(
    page_title="Tesouraria Igreja - Controle Financeiro",
    page_icon="📊",
    layout="wide"
)

CAMINHO_BASE = "dados/base_consolidada.csv"
CAMINHO_DIZIMISTAS = "dados/dizimistas.csv"
CAMINHO_CONFIG = "dados/config.json"

# Garantir existência da pasta de dados
if not os.path.exists("dados"):
    os.makedirs("dados")

# --- GERENCIAMENTO DO ARQUIVO JSON (CONFIGURAÇÕES) ---
def carregar_config():
    if os.path.exists(CAMINHO_CONFIG) and os.path.getsize(CAMINHO_CONFIG) > 0:
        with open(CAMINHO_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        config_padrao = {
            "nome_igreja": "Primeirra Igreja Batista Luz do Mundo",
            "tesoureiro": "Elizane Batista Sobrinho",
            "vice_tesoureiro": "Maria Rita de Cassia Da Silva Leão",
            "categorias_entrada": ["Dízimo", "Oferta Geral", "Oferta Missões", "Oferta de Obras/Construção"],
            "categorias_saida": ["Manutenção e Obras", "Energia e Água", "Prebenda Pastoral / Pessoal", "Ação Social", "Material de Escritório / Impressos", "Aluguel / Encargos", "Ministério de Louvor / Música", "Outras Despesas"]
        }
        with open(CAMINHO_CONFIG, "w", encoding="utf-8") as f:
            json.dump(config_padrao, f, ensure_ascii=False, indent=2)
        return config_padrao

# --- CARGA E SALVAMENTO DE DADOS CSV (COM PROTEÇÃO CONTRA ARQUIVO VAZIO) ---
def carregar_dados():
    if os.path.exists(CAMINHO_BASE) and os.path.getsize(CAMINHO_BASE) > 0:
        try:
            df = pd.read_csv(CAMINHO_BASE)
            df['data'] = pd.to_datetime(df['data'])
            
            # Garantir colunas obrigatórias caso o CSV seja antigo
            if 'id_dizimista' not in df.columns:
                df['id_dizimista'] = 0
            if 'qtd_dizimistas' not in df.columns:
                df['qtd_dizimistas'] = 0
                
            return df
        except Exception:
            return pd.DataFrame(columns=[
                'id', 'data', 'mes_referencia', 'origem', 'tipo_movimento', 
                'categoria', 'descricao', 'valor', 'qtd_dizimistas', 'id_dizimista'
            ])
    else:
        return pd.DataFrame(columns=[
            'id', 'data', 'mes_referencia', 'origem', 'tipo_movimento', 
            'categoria', 'descricao', 'valor', 'qtd_dizimistas', 'id_dizimista'
        ])

def reescrever_dados_completos(df_novo):
    df_novo.to_csv(CAMINHO_BASE, index=False)

def salvar_dados(novos_dados):
    df_atual = carregar_dados()
    df_unificado = pd.concat([df_atual, pd.DataFrame(novos_dados)], ignore_index=True)
    reescrever_dados_completos(df_unificado)

def carregar_dizimistas():
    if os.path.exists(CAMINHO_DIZIMISTAS) and os.path.getsize(CAMINHO_DIZIMISTAS) > 0:
        try:
            return pd.read_csv(CAMINHO_DIZIMISTAS)
        except Exception:
            return pd.DataFrame(columns=['id_dizimista', 'nome', 'telefone'])
    else:
        return pd.DataFrame(columns=['id_dizimista', 'nome', 'telefone'])

def reescrever_dizimistas_completos(df_diz):
    df_diz.to_csv(CAMINHO_DIZIMISTAS, index=False)

def salvar_dizimista(nome, telefone):
    df = carregar_dizimistas()
    novo_id = len(df) + 1 if df.empty else int(df['id_dizimista'].max()) + 1
    novo_df = pd.concat([df, pd.DataFrame([{'id_dizimista': novo_id, 'nome': nome, 'telefone': telefone}])], ignore_index=True)
    reescrever_dizimistas_completos(novo_df)

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

# Carregar estados iniciais
config = carregar_config()
df_base = carregar_dados()
df_dizimistas = carregar_dizimistas()

# Dicionário auxiliar para selectbox de dizimistas
opcoes_dizimistas = {0: "Anônimo / Não Identificado"}
for _, row in df_dizimistas.iterrows():
    opcoes_dizimistas[int(row['id_dizimista'])] = f"{row['nome']} (ID: {int(row['id_dizimista'])})"

st.title(f"📊 Tesouraria — {config['nome_igreja']}")

# -------------------------------------------------------------------
# MENU LATERAL: NAVEGAÇÃO E CONFIGURAÇÃO DA IGREJA
# -------------------------------------------------------------------
st.sidebar.header("Gestão & Ações")
opcao_sidebar = st.sidebar.radio("Navegação", [
    "Visualizar Dashboards", 
    "Lançar Espécie (Culto)", 
    "Importar Extrato OFX",
    "Editar / Excluir Lançamentos",
    "Cadastrar / Editar Dizimistas",
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
                    df_dizimistas.loc[df_dizimistas['id_dizimista'] == id_sel_edit, 'nome'] = novo_nome.strip()
                    df_dizimistas.loc[df_dizimistas['id_dizimista'] == id_sel_edit, 'telefone'] = novo_tel.strip()
                    reescrever_dizimistas_completos(df_dizimistas)
                    st.success("Cadastro atualizado com sucesso!")
                    st.rerun()

                if btn_deletar:
                    df_dizimistas = df_dizimistas[df_dizimistas['id_dizimista'] != id_sel_edit]
                    reescrever_dizimistas_completos(df_dizimistas)
                    st.warning("Dizimista excluído com sucesso!")
                    st.rerun()

# 2. LANÇAMENTO EM ESPÉCIE
elif opcao_sidebar == "Lançar Espécie (Culto)":
    st.header("Fechamento em Espécie por Culto")
    with st.form("form_especie", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        data_culto = c1.date_input("Data do Culto", datetime.now())
        mes_ref = c2.text_input("Mês de Competência (YYYY-MM)", value=datetime.now().strftime("%Y-%m"))
        turno = c3.selectbox("Evento / Turno", ["Domingo Noite", "Domingo Manhã", "Culto de Ensino", "Eventos / Outros"])
        
        st.subheader("Valores Contados")
        v_dizimos = st.number_input("Total em Dízimos (Espécie)", min_value=0.0, step=10.0, format="%.2f")
        id_diz_sel = st.selectbox("Vincular a Dizimista Específico (Opcional)", 
                                  options=list(opcoes_dizimistas.keys()), 
                                  format_func=lambda x: opcoes_dizimistas[x])
        
        v_ofertas = st.number_input("Total em Ofertas Gerais (Espécie)", min_value=0.0, step=10.0, format="%.2f")
        v_missoes = st.number_input("Total em Ofertas de Missões", min_value=0.0, step=10.0, format="%.2f")
        responsaveis = st.text_input("Responsáveis pela Contagem", value=config['tesoureiro'])
        
        if st.form_submit_button("Gravar Fechamento"):
            novos_registros = []
            agora_str = datetime.now().strftime("%Y%m%d%H%M%S")

            if v_dizimos > 0:
                novos_registros.append({
                    'id': f"ESP-{agora_str}-1", 'data': data_culto, 'mes_referencia': mes_ref,
                    'origem': 'Espécie', 'tipo_movimento': 'Entrada', 'categoria': 'Dízimo',
                    'descricao': f"Dízimos em espécie - {turno} (Resp: {responsaveis})",
                    'valor': v_dizimos, 'qtd_dizimistas': 1 if id_diz_sel != 0 else 0,
                    'id_dizimista': id_diz_sel
                })
            if v_ofertas > 0:
                novos_registros.append({
                    'id': f"ESP-{agora_str}-2", 'data': data_culto, 'mes_referencia': mes_ref,
                    'origem': 'Espécie', 'tipo_movimento': 'Entrada', 'categoria': 'Oferta Geral',
                    'descricao': f"Oferta em espécie - {turno}", 'valor': v_ofertas, 
                    'qtd_dizimistas': 0, 'id_dizimista': 0
                })
            if v_missoes > 0:
                novos_registros.append({
                    'id': f"ESP-{agora_str}-3", 'data': data_culto, 'mes_referencia': mes_ref,
                    'origem': 'Espécie', 'tipo_movimento': 'Entrada', 'categoria': 'Oferta Missões',
                    'descricao': f"Oferta Missões em espécie - {turno}", 'valor': v_missoes, 
                    'qtd_dizimistas': 0, 'id_dizimista': 0
                })

            if novos_registros:
                salvar_dados(novos_registros)
                st.success("Lançamento salvo com sucesso!")
                st.rerun()

# 3. IMPORTAR EXTRATO OFX (CORRIGIDO PARA SALVAR AS SELEÇÕES)
elif opcao_sidebar == "Importar Extrato OFX":
    st.header("Importação de Extrato Bancário (.ofx)")
    col_i1, col_i2 = st.columns(2)
    mes_referencia_upload = col_i1.text_input("Mês de Competência (YYYY-MM)", value=datetime.now().strftime("%Y-%m"))
    arquivo_ofx = col_i2.file_uploader("Selecione o arquivo .OFX fornecido pelo banco", type=["ofx"])

    if arquivo_ofx is not None:
        try:
            df_ofx = extrair_dados_ofx(arquivo_ofx)
            st.subheader(f"Classificação das Transações — Total: {len(df_ofx)} itens")

            categorias_todas = config["categorias_entrada"] + config["categorias_saida"]

            # Formulário com leitura correta dos widgets através das chaves (keys)
            with st.form("form_conciliacao_ofx"):
                for idx, row in df_ofx.iterrows():
                    st.markdown(f"**Item #{idx+1}:** {row['descricao']} — **R$ {row['valor']:,.2f}** ({row['tipo_movimento']})")
                    c1, c2, c3, c4 = st.columns(4)
                    
                    c1.date_input(f"Data #{idx+1}", row['data'], key=f"data_ofx_{idx}")
                    idx_tipo = 0 if row['tipo_movimento'] == 'Entrada' else 1
                    c2.selectbox(f"Tipo #{idx+1}", ["Entrada", "Saída"], index=idx_tipo, key=f"tipo_ofx_{idx}")
                    c3.selectbox(f"Categoria #{idx+1}", categorias_todas, key=f"cat_ofx_{idx}")
                    c4.selectbox(f"Dizimista #{idx+1}", options=list(opcoes_dizimistas.keys()), format_func=lambda x: opcoes_dizimistas[x], key=f"diz_ofx_{idx}")
                    
                    st.divider()

                btn_confirmar_ofx = st.form_submit_button(f"Confirmar Extrato {mes_referencia_upload}")

                if btn_confirmar_ofx:
                    dados_conciliados = []
                    agora_str = datetime.now().strftime("%Y%m%d%H%M%S")

                    # Ler os valores selecionados diretamente das chaves do Streamlit (st.session_state)
                    for idx, row in df_ofx.iterrows():
                        dt_sel = st.session_state[f"data_ofx_{idx}"]
                        tp_sel = st.session_state[f"tipo_ofx_{idx}"]
                        cat_sel = st.session_state[f"cat_ofx_{idx}"]
                        diz_sel = st.session_state[f"diz_ofx_{idx}"]

                        dados_conciliados.append({
                            'id': f"BNK-{agora_str}-{idx}",
                            'data': pd.to_datetime(dt_sel),
                            'mes_referencia': mes_referencia_upload,
                            'origem': 'Banco (OFX)',
                            'tipo_movimento': tp_sel,
                            'categoria': cat_sel,
                            'descricao': row['descricao'],
                            'valor': float(row['valor']),
                            'qtd_dizimistas': 1 if diz_sel != 0 else 0,
                            'id_dizimista': int(diz_sel)
                        })

                    salvar_dados(dados_conciliados)
                    st.success(f"✅ Extrato do mês {mes_referencia_upload} salvo com sucesso! Os relatórios foram atualizados.")
                    st.rerun()

        except Exception as e:
            st.error(f"Erro ao processar o arquivo OFX: {e}")

# 4. EDITAR / EXCLUIR LANÇAMENTOS
elif opcao_sidebar == "Editar / Excluir Lançamentos":
    st.header("✏️ Editar ou Excluir Lançamentos Financeiros")
    
    if df_base.empty:
        st.info("Nenhum lançamento registrado na base.")
    else:
        # Garantir que a coluna id_dizimista existe no DataFrame carregado
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

            # Formulário de Edição
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
                
                # Leitura segura de id_dizimista
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
                    df_base.loc[df_base['id'] == id_selecionado, 'data'] = pd.to_datetime(dt_edit)
                    df_base.loc[df_base['id'] == id_selecionado, 'mes_referencia'] = mes_ref_edit
                    df_base.loc[df_base['id'] == id_selecionado, 'origem'] = origem_edit
                    df_base.loc[df_base['id'] == id_selecionado, 'tipo_movimento'] = tipo_edit
                    df_base.loc[df_base['id'] == id_selecionado, 'categoria'] = cat_edit
                    df_base.loc[df_base['id'] == id_selecionado, 'valor'] = val_edit
                    df_base.loc[df_base['id'] == id_selecionado, 'descricao'] = desc_edit
                    df_base.loc[df_base['id'] == id_selecionado, 'id_dizimista'] = diz_edit
                    df_base.loc[df_base['id'] == id_selecionado, 'qtd_dizimistas'] = 1 if diz_edit != 0 else 0

                    reescrever_dados_completos(df_base)
                    st.success("Lançamento atualizado com sucesso!")
                    st.rerun()

            # Botão de exclusão fora do formulário de edição para evitar conflito
            st.divider()
            if st.button("🗑 Excluir Este Lançamento (Ação Irreversível)", type="secondary"):
                df_base = df_base[df_base['id'] != id_selecionado]
                reescrever_dados_completos(df_base)
                st.warning("Lançamento removido com sucesso!")
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

# -------------------------------------------------------------------
# VISUALIZAÇÃO POR ABAS DINÂMICAS
# -------------------------------------------------------------------
elif opcao_sidebar == "Visualizar Dashboards":
    if df_base.empty:
        st.info("Nenhum registro cadastrado na base.")
    else:
        meses_lista = sorted(df_base['mes_referencia'].unique())
        nomes_abas = [f"Mês: {m}" for m in meses_lista] + ["📈 Relatório Final & DRE", "👤 Ficha do Dizimista"]
        abas = st.tabs(nomes_abas)

        # Abas dos Meses
        for idx, mes in enumerate(meses_lista):
            with abas[idx]:
                st.header(f"Mês: {mes}")
                df_mes = df_base[df_base['mes_referencia'] == mes]

                entradas_mes = df_mes[df_mes['tipo_movimento'] == 'Entrada']['valor'].sum()
                saidas_mes = df_mes[df_mes['tipo_movimento'] == 'Saída']['valor'].sum()

                m1, m2, m3 = st.columns(3)
                m1.metric("Entradas", f"R$ {entradas_mes:,.2f}")
                m2.metric("Saídas", f"R$ {saidas_mes:,.2f}")
                m3.metric("Resultado Mensal", f"R$ {(entradas_mes - saidas_mes):,.2f}")

                st.divider()

                g1, g2 = st.columns(2)
                with g1:
                    st.subheader("Entradas")
                    df_ent = df_mes[df_mes['tipo_movimento'] == 'Entrada']
                    if not df_ent.empty:
                        st.plotly_chart(px.pie(df_ent, names='categoria', values='valor', hole=0.3), use_container_width=True)
                with g2:
                    st.subheader("Despesas")
                    df_sai = df_mes[df_mes['tipo_movimento'] == 'Saída']
                    if not df_sai.empty:
                        st.plotly_chart(px.bar(df_sai.groupby('categoria')['valor'].sum().reset_index(), x='valor', y='categoria', orientation='h'), use_container_width=True)

                st.subheader("Lançamentos do Mês")
                st.dataframe(df_mes[['id', 'data', 'origem', 'tipo_movimento', 'categoria', 'descricao', 'valor', 'id_dizimista']], use_container_width=True)

        # Aba Relatório Final & DRE
        with abas[-2]:
            st.header("📈 Relatório Comparativo Final")
            tot_ent = df_base[df_base['tipo_movimento'] == 'Entrada']['valor'].sum()
            tot_sai = df_base[df_base['tipo_movimento'] == 'Saída']['valor'].sum()

            c1, c2, c3 = st.columns(3)
            c1.metric("Entradas Totais", f"R$ {tot_ent:,.2f}")
            c2.metric("Saídas Totais", f"R$ {tot_sai:,.2f}")
            c3.metric("Superávit / Déficit Acumulado", f"R$ {(tot_ent - tot_sai):,.2f}")

            st.divider()
            
            st.subheader("DRE Comparativa (Visão Contábil por Mês)")
            dre_pivot = df_base.pivot_table(index=['tipo_movimento', 'categoria'], columns='mes_referencia', values='valor', aggfunc='sum', fill_value=0)
            st.dataframe(dre_pivot.style.format("R$ {:,.2f}"), use_container_width=True)

        # Aba Ficha do Dizimista
        with abas[-1]:
            st.header("👤 Extrato Individual por Dizimista")
            if df_dizimistas.empty:
                st.info("Nenhum dizimista cadastrado na base.")
            else:
                dizimista_selecionado = st.selectbox(
                    "Selecione o Dizimista para consultar o extrato:", 
                    options=df_dizimistas['id_dizimista'].tolist(),
                    format_func=lambda id_d: df_dizimistas[df_dizimistas['id_dizimista'] == id_d]['nome'].values[0]
                )

                if dizimista_selecionado:
                    info_membro = df_dizimistas[df_dizimistas['id_dizimista'] == dizimista_selecionado].iloc[0]
                    df_membro = df_base[df_base['id_dizimista'] == dizimista_selecionado]

                    st.markdown(f"### **Membro:** {info_membro['nome']}")
                    if pd.notna(info_membro['telefone']):
                        st.caption(f"Contato: {info_membro['telefone']}")

                    tot_contrib = df_membro['valor'].sum()
                    qtd_contrib = len(df_membro)

                    k1, k2 = st.columns(2)
                    k1.metric("Total Contribuído", f"R$ {tot_contrib:,.2f}")
                    k2.metric("Lançamentos Registrados", qtd_contrib)

                    st.divider()
                    st.subheader("Histórico de Contribuições")
                    if df_membro.empty:
                        st.write("Nenhum lançamento vinculado a este membro.")
                    else:
                        st.dataframe(
                            df_membro[['data', 'mes_referencia', 'origem', 'categoria', 'descricao', 'valor']],
                            use_container_width=True
                        )