import os
import json
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response # Adicione Response
import io 
import csv 
# --- Configuração da Aplicação Flask ---
app = Flask(__name__)
# A 'secret_key' é necessária para gerenciar sessões de login de forma segura.
app.secret_key = 'uma-chave-secreta-muito-dificil-de-adivinhar'

# --- Constantes e Configurações ---
NOME_ARQUIVO_DADOS = 'dados_empresas.json'
USUARIO_PADRAO = 'admin'
SENHA_PADRAO = 'contajur2025'

# --- Listas de Campos para facilitar a iteração ---
CAMPOS_FATURAMENTO = [
    "Serviços tributados", "Serviços retidos", "Venda (indústria)",
    "Revenda mercadorias tributárias", "Revenda mercadorias não tributárias"
]
CAMPOS_IMPOSTOS = [
    "Simples", "PIS", "COFINS", "IR", "CSLL", "ICMS Próprio", 
    "ICMS ST", "ISSQN a pagar", "ISSQN retido sobre faturamento"
]
CAMPOS_DESPESAS = [
    "Compras para revenda: DIFAL", "Compras para revenda: FEM", "Compras para revenda: ICMS ST",
    "Compras para uso/consumo/ativo: DIFAL", "Compras para uso/consumo: FEM", "Compras para uso/consumo: ICMS ST",
    "Serviços tomados: IRRF", "Serviços tomados: CSRF", "Serviços tomados: INSS", 
    "Serviços tomados: ISSQN Retido"
]

# --- Funções Auxiliares de Dados ---
def carregar_dados():
    """Carrega os dados do arquivo JSON."""
    if not os.path.exists(NOME_ARQUIVO_DADOS):
        return {}
    with open(NOME_ARQUIVO_DADOS, 'r', encoding='utf-8') as f:
        return json.load(f)

def salvar_dados(dados):
    """Salva os dados no arquivo JSON."""
    with open(NOME_ARQUIVO_DADOS, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def para_float(valor_str):
    """Converte uma string para float, tratando vírgulas e valores vazios."""
    if not valor_str:
        return 0.0
    try:
        # Substitui vírgula por ponto para conversão correta
        return float(str(valor_str).replace(',', '.'))
    except (ValueError, TypeError):
        return 0.0

# --- Decorador de Autenticação ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Rotas da Aplicação (As "Páginas" do site) ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['username']
        senha = request.form['password']
        if usuario == USUARIO_PADRAO and senha == SENHA_PADRAO:
            session['logged_in'] = True
            session['username'] = usuario
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    dados = carregar_dados()
    empresas = sorted(dados.keys())
    
    # Para preencher os seletores de data
    now = datetime.now()
    meses = [f"{i:02d}" for i in range(1, 13)]
    anos = [str(i) for i in range(now.year - 5, now.year + 2)]
    
    return render_template('index.html', empresas=empresas, meses=meses, anos=anos, ano_atual=str(now.year), mes_atual=f"{now.month:02d}")

@app.route('/add_company', methods=['POST'])
@login_required
def add_company():
    nome_empresa = request.form.get('nome_empresa')
    if not nome_empresa:
        flash('O nome da empresa não pode ser vazio.', 'danger')
        return redirect(url_for('index'))
    
    dados = carregar_dados()
    if nome_empresa in dados:
        flash('Essa empresa já está cadastrada.', 'warning')
    else:
        dados[nome_empresa] = {}
        salvar_dados(dados)
        flash(f'Empresa "{nome_empresa}" adicionada com sucesso!', 'success')
        
    return redirect(url_for('index'))

@app.route('/dados/<path:nome_empresa>/<periodo>', methods=['GET', 'POST'])
@login_required
def dados_empresa(nome_empresa, periodo):
    dados_gerais = carregar_dados()
    if nome_empresa not in dados_gerais:
        flash('Empresa não encontrada.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Inicializa a estrutura de dados se não existir
        if periodo not in dados_gerais[nome_empresa]:
            dados_gerais[nome_empresa][periodo] = {}
        
        # Coleta e valida dados do formulário
        dados_periodo = dados_gerais[nome_empresa][periodo]
        dados_periodo['faturamento'] = {campo: para_float(request.form.get(campo)) for campo in CAMPOS_FATURAMENTO}
        dados_periodo['impostos'] = {campo: para_float(request.form.get(campo)) for campo in CAMPOS_IMPOSTOS}
        dados_periodo['despesas'] = {campo: para_float(request.form.get(campo)) for campo in CAMPOS_DESPESAS}
        
        salvar_dados(dados_gerais)
        flash(f'Dados para {nome_empresa} ({periodo}) salvos com sucesso!', 'success')
        return redirect(url_for('index'))

    # Método GET: Exibe o formulário com dados existentes
    dados_atuais = dados_gerais[nome_empresa].get(periodo, {})
    return render_template('dados_empresa.html', 
                           nome_empresa=nome_empresa, 
                           periodo=periodo,
                           dados=dados_atuais,
                           campos_faturamento=CAMPOS_FATURAMENTO,
                           campos_impostos=CAMPOS_IMPOSTOS,
                           campos_despesas=CAMPOS_DESPESAS)

@app.route('/export_csv')
@login_required
def export_csv():
    """Gera um arquivo CSV com todos os dados e o serve para download."""
    dados = carregar_dados()

    # Define o nome do arquivo com a data atual
    timestamp = datetime.now().strftime("%Y-%m-%d")
    filename = f"export_contajur_{timestamp}.csv"

    # Prepara os dados para o formato tabular (lista de dicionários)
    linhas_para_csv = []
    for nome_empresa, periodos in dados.items():
        for periodo, categorias in periodos.items():
            if not isinstance(categorias, dict): continue # Pula períodos malformados

            ano, mes = periodo.split('-')
            
            # Cria uma linha base com informações da empresa e período
            linha = {
                'Empresa': nome_empresa,
                'Ano': ano,
                'Mes': mes
            }
            # Adiciona os dados de cada categoria à linha, tratando campos ausentes
            linha.update(categorias.get('faturamento', {}))
            linha.update(categorias.get('impostos', {}))
            linha.update(categorias.get('despesas', {}))
            
            linhas_para_csv.append(linha)
    
    if not linhas_para_csv:
        flash('Não há dados para exportar.', 'warning')
        return redirect(url_for('index'))

    # Usa um buffer de string em memória para criar o CSV
    output = io.StringIO()
    
    # Define os cabeçalhos do CSV na ordem desejada
    headers = ['Empresa', 'Ano', 'Mes'] + CAMPOS_FATURAMENTO + CAMPOS_IMPOSTOS + CAMPOS_DESPESAS
    
    # O DictWriter é ótimo pois lida com dicionários e garante que os valores
    # sejam escritos nas colunas corretas, mesmo que uma linha não tenha um campo.
    writer = csv.DictWriter(output, fieldnames=headers)
    
    # Escreve o cabeçalho
    writer.writeheader()
    
    # Escreve todas as linhas de dados
    writer.writerows(linhas_para_csv)
    
    # Prepara a resposta do Flask para o download
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

@app.route('/delete/<path:nome_empresa>')
@login_required
def delete_company(nome_empresa):
    """Exclui uma empresa e todos os seus dados do arquivo JSON."""
    dados = carregar_dados()
    
    if nome_empresa in dados:
        # Remove a chave correspondente à empresa do dicionário
        del dados[nome_empresa]
        salvar_dados(dados)
        flash(f'Empresa "{nome_empresa}" e todos os seus dados foram excluídos com sucesso.', 'success')
    else:
        flash(f'Erro: Empresa "{nome_empresa}" não encontrada.', 'danger')
        
    return redirect(url_for('index'))

if __name__ == '__main__':
    
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port)
