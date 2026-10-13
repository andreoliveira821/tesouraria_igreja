import streamlit_authenticator as stauth

nova_senha_hash = stauth.Hasher.hash('teste321')
print(nova_senha_hash)