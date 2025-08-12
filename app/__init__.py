# app/__init__.py
from flask import Flask

# Cria a instância da aplicação
app = Flask(__name__)

# Carrega as configurações do arquivo config.py
app.config.from_object('app.config')

# Importa as rotas para que sejam registradas na aplicação
from app import routes
