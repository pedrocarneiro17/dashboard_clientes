# app/utils.py
import os
import json
from functools import wraps
from flask import session, flash, redirect, url_for

# A importação de NOME_ARQUIVO_DADOS foi removida.
# As funções carregar_dados e salvar_dados foram removidas.

def para_float(valor):
    """Converte uma string monetária ou um número para float."""
    if isinstance(valor, (int, float)):
        return float(valor)
    if not valor:
        return 0.0
    try:
        s = str(valor).replace('R$', '').strip().replace('.', '')
        s = s.replace(',', '.')
        return float(s)
    except (ValueError, TypeError):
        return 0.0

def login_required(f):
    """Decorador para exigir login em certas rotas."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('main.login')) # O nome da rota de login foi corrigido para 'main.login'
        return f(*args, **kwargs)
    return decorated_function