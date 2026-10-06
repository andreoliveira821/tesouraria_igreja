# 📊 Sistema de Tesouraria e Gestão Financeira para Igrejas

Aplicação web desenvolvida em **Python** e **Streamlit** para automação, controle contábil e gestão financeira de igrejas locais. O sistema oferece conciliação bancária via extratos `.OFX`, controle de dizimistas, lançamento de fechamentos de cultos em espécie e geração automática de demonstrativos financeiros (DRE).

---

## 🚀 Funcionalidades Principais

* **📊 Dashboards Dinâmicos:** Visualização mensal automatizada com indicadores de entradas, saídas, saldos e gráficos explicativos.
* **🏦 Conciliação Bancária OFX:** Importação direta do extrato bancário fornecido pelo banco (`.ofx`) com categorização rápida e vínculo de membros.
* **💵 Lançamento em Espécie por Culto:** Registro agrupado de dízimos e ofertas arrecadados presencialmente nos cultos e eventos.
* **👤 Gestão de Dizimistas:** Cadastro e consulta de ficha individual com histórico completo de contribuições por membro.
* **✏️ Edição e Exclusão Segura:** Interface para alteração rápida e correção de dados lançados erroneamente.
* **📈 DRE & Relatório Comparativo:** Demonstrativo do Resultado do Exercício comparativo entre os meses para apoio à tomada de decisão.
* **⚙️ Configuração Personalizada:** Edição flexível de categorias de receita, despesa e dados da igreja salvos em arquivo `JSON`.

---

## 🛠️ Tecnologias Utilizadas

* **[Python 3.10+](https://www.python.org/)** — Linguagem principal.
* **[Streamlit](https://streamlit.io/)** — Interface web interativa.
* **[Pandas](https://pandas.pydata.org/)** — Processamento e manipulação de dados.
* **[Plotly Express](https://plotly.com/python/)** — Gráficos interativos.
* **[ofxparse](https://github.com/jseutter/ofxparse)** — Parser para arquivos de extrato bancário `.OFX`.

---

## 📁 Estrutura do Projeto

```text
tesouraria_igreja/
│
├── app.py                   # Código principal da aplicação Streamlit
├── requirements.txt         # Dependências do projeto
├── README.md                # Documentação do projeto
├── .gitignore               # Arquivos ignorados pelo Git (proteção de dados)
└── dados/                   # Armazenamento local (gerado automaticamente)
    ├── base_consolidada.csv # Lançamentos financeiros
    ├── dizimistas.csv       # Cadastro de membros
    └── config.json          # Configurações do sistema
```

---

## 🔧 Como Executar o Projeto Localmente

### 1. Pré-requisitos
Certifique-se de ter o **Python 3.10+** instalado na sua máquina.

### 2. Clonar o Repositório
```bash
git clone https://github.com/seu-usuario/tesouraria-igreja.git
cd tesouraria-igreja
```

### 3. Criar e Ativar um Ambiente Virtual (Opcional, mas recomendado)
* **Windows:**
  ```bash
  python -m venv venv
  .\venv\Scripts\activate
  ```
* **Linux/macOS:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 4. Instalar as Dependências
Caso ainda não tenha o `requirements.txt`, instale os pacotes principais:
```bash
pip install streamlit pandas plotly ofxparse
```

### 5. Executar a Aplicação
```bash
streamlit run app.py
```
O sistema abrirá automaticamente no seu navegador no endereço: `http://localhost:8501`.

---

## 🔒 Segurança de Dados

O arquivo `.gitignore` deste repositório está configurado para **impedir a submissão dos dados locais (`dados/`)** para o GitHub, garantindo a privacidade e sigilo das informações financeiras da igreja.

---

## 📝 Licença

Este projeto está sob a licença MIT. Sinta-se livre para adaptar e utilizar na sua igreja local!