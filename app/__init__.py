# app/__init__.py
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# Cria a instância da aplicação
app = Flask(__name__)

# Carrega as configurações do arquivo config.py
app.config.from_object('app.config')

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
# Lê a URL do banco de dados da variável de ambiente (para o Railway).
# Se não encontrar, usa um banco de dados local chamado 'local.db' para desenvolvimento.
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Cria a instância do banco de dados e a liga à nossa aplicação
db = SQLAlchemy(app)

# --- MODELOS DE DADOS ---
# Movido para aqui para evitar importações circulares
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Empresa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    cnpj = db.Column(db.String(18))
    envio_imposto = db.Column(db.String(50))
    prazo = db.Column(db.String(10))
    active = db.Column(db.Boolean, default=True)
    periodos = db.relationship('Periodo', backref='empresa', lazy=True, cascade="all, delete-orphan")

class Periodo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ano_mes = db.Column(db.String(7), nullable=False) # ex: "2025-08"
    status = db.Column(db.String(20), default='Em Aberto')
    dp_status = db.Column(db.String(20), default='Em Aberto')
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False)
    
    # Usaremos JSON para manter a flexibilidade dos dados fiscais e de DP por enquanto
    dados_fiscais = db.Column(db.JSON)
    dados_dp = db.Column(db.JSON)

# Importa e registra os Blueprints (depois de 'db' e dos modelos estarem definidos)
from app.main.routes import main_bp
from app.company.routes import company_bp
from app.fiscal.routes import fiscal_bp
from app.dp.routes import dp_bp
from app.dashboard.routes import dashboard_bp 

app.register_blueprint(main_bp)
app.register_blueprint(company_bp)
app.register_blueprint(fiscal_bp)
app.register_blueprint(dp_bp)
app.register_blueprint(dashboard_bp)