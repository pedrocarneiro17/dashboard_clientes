# app/utils.py
import os
import json
from functools import wraps
from flask import session, flash, redirect, url_for
from .config import NOME_ARQUIVO_DADOS

def carregar_dados():
    """Carrega os dados do arquivo JSON."""
    if not os.path.exists(NOME_ARQUIVO_DADOS): return {}
    try:
        with open(NOME_ARQUIVO_DADOS, 'r', encoding='utf-8') as f: return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError): return {}

def salvar_dados(dados):
    """Salva os dados no arquivo JSON."""
    with open(NOME_ARQUIVO_DADOS, 'w', encoding='utf-8') as f: json.dump(dados, f, indent=4, ensure_ascii=False)

def para_float(valor_str):
    """Converte uma string para float, tratando vírgulas e valores vazios."""
    if not valor_str: return 0.0
    try: return float(str(valor_str).replace(',', '.'))
    except (ValueError, TypeError): return 0.0

def login_required(f):
    """Decorador para exigir login em certas rotas."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
