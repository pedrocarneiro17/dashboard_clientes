import os
import json
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
import io
from openpyxl import Workbook
from io import BytesIO

# --- Configuração da Aplicação Flask ---
app = Flask(__name__)
app.secret_key = 'uma-chave-secreta-muito-dificil-de-adivinhar'

# --- Constantes e Configurações ---
NOME_ARQUIVO_DADOS = 'dados_empresas.json'
USUARIO_PADRAO = 'admin'
SENHA_PADRAO = 'contajur2025'

# --- Listas de Campos ---
CAMPOS_FATURAMENTO = [
    "Serviços tributados", "Serviços retidos", "Venda (indústria)",
    "Revenda mercadorias tributárias", "Revenda mercadorias não tributárias",
    "Revenda de mercadoria monofásica", "Locação"
]
CAMPOS_DESPESAS = [
    "Compras para revenda", "Compras para uso/consumo",
    "Compras para ativo imobilizado", "Serviços tomados com nota fiscal"
]
CAMPOS_IMPOSTOS_FEDERAL = ["Simples", "PIS", "COFINS", "IRPJ", "CSLL"]
CAMPOS_IMPOSTOS_ESTADUAL = ["ICMS próprio", "ICMS ST próprio", "DIFAL", "Antecipação", "ICMS ST Entradas", "FEM"]
CAMPOS_IMPOSTOS_MUNICIPAL = ["ISSQN a pagar", "ISSQN Retido (NF própria)"]
CAMPOS_RETENCOES_FEDERAL = ["CSRF (Retido)", "IRRF (Retido)", "INSS (Retido)", "ISSQN (Retido)"]

# --- Funções Auxiliares de Dados ---
def carregar_dados():
    if not os.path.exists(NOME_ARQUIVO_DADOS): return {}
    try:
        with open(NOME_ARQUIVO_DADOS, 'r', encoding='utf-8') as f: return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError): return {}

def salvar_dados(dados):
    with open(NOME_ARQUIVO_DADOS, 'w', encoding='utf-8') as f: json.dump(dados, f, indent=4, ensure_ascii=False)

def para_float(valor_str):
    if not valor_str: return 0.0
    try: return float(str(valor_str).replace(',', '.'))
    except (ValueError, TypeError): return 0.0

# --- Decorador de Autenticação ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Rotas da Aplicação ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == USUARIO_PADRAO and request.form['password'] == SENHA_PADRAO:
            session['logged_in'] = True
            session['username'] = request.form['username']
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
    empresas_ativas = {nome: detalhes for nome, detalhes in dados.items() if detalhes.get('active', True)}
    empresas_ordenadas = dict(sorted(empresas_ativas.items()))
    
    search_ano = request.args.get('search_ano')
    search_mes = request.args.get('search_mes')
    empresas_em_aberto = None
    empresas_finalizadas = None
    periodo_pesquisado = None

    if search_ano and search_mes:
        periodo_pesquisado = f"{search_ano}-{search_mes}"
        empresas_em_aberto = []
        empresas_finalizadas = []
        for nome, detalhes in empresas_ordenadas.items():
            periodos = detalhes.get('periodos', {})
            status_do_periodo = periodos.get(periodo_pesquisado, {}).get('status', 'Em Aberto')
            
            if status_do_periodo == 'Finalizado':
                empresas_finalizadas.append(nome)
            else:
                empresas_em_aberto.append(nome)

    now = datetime.now()
    meses = [f"{i:02d}" for i in range(1, 13)]
    anos = [str(i) for i in range(2010, now.year + 6)]
    
    return render_template('index.html', 
                           empresas=empresas_ordenadas, 
                           meses=meses, anos=anos, 
                           ano_atual=str(now.year), mes_atual=f"{now.month:02d}",
                           empresas_em_aberto=empresas_em_aberto,
                           empresas_finalizadas=empresas_finalizadas,
                           periodo_pesquisado=periodo_pesquisado,
                           search_ano=search_ano, search_mes=search_mes)

@app.route('/add_company_page')
@login_required
def add_company_page():
    return render_template('add_company.html')

@app.route('/add_company', methods=['POST'])
@login_required
def add_company():
    nome_empresa = request.form.get('nome_empresa')
    if not nome_empresa:
        flash('O nome da empresa não pode ser vazio.', 'danger')
        return redirect(url_for('add_company_page'))
    dados = carregar_dados()
    if nome_empresa in dados:
        flash('Essa empresa já está cadastrada.', 'warning')
        return redirect(url_for('add_company_page'))
    
    dados[nome_empresa] = {
        'cnpj': request.form.get('cnpj', ''),
        'envio_imposto': request.form.get('envio_imposto', ''),
        'prazo': request.form.get('prazo', ''),
        'active': True,
        'periodos': {}
    }
    salvar_dados(dados)
    flash(f'Empresa "{nome_empresa}" adicionada com sucesso!', 'success')
    return redirect(url_for('index'))

# --- ROTA PARA A NOVA PÁGINA DE SELEÇÃO ---
@app.route('/select_company_to_edit_page')
@login_required
def select_company_to_edit_page():
    dados = carregar_dados()
    empresas_ativas = {nome: detalhes for nome, detalhes in dados.items() if detalhes.get('active', True)}
    empresas_ordenadas = dict(sorted(empresas_ativas.items()))
    return render_template('select_company_to_edit.html', empresas=empresas_ordenadas)

@app.route('/edit_company_page/<path:nome_empresa>')
@login_required
def edit_company_page(nome_empresa):
    dados = carregar_dados()
    empresa = dados.get(nome_empresa)
    if not empresa:
        flash('Empresa não encontrada.', 'danger')
        return redirect(url_for('index'))
    return render_template('edit_company.html', nome_empresa=nome_empresa, empresa=empresa)

@app.route('/update_company/<path:nome_empresa>', methods=['POST'])
@login_required
def update_company(nome_empresa):
    dados = carregar_dados()
    if nome_empresa not in dados:
        flash('Empresa não encontrada.', 'danger')
        return redirect(url_for('index'))
    
    dados[nome_empresa]['cnpj'] = request.form.get('cnpj', '')
    dados[nome_empresa]['envio_imposto'] = request.form.get('envio_imposto', '')
    dados[nome_empresa]['prazo'] = request.form.get('prazo', '')
    
    salvar_dados(dados)
    flash(f'Dados da empresa "{nome_empresa}" atualizados com sucesso!', 'success')
    return redirect(url_for('index'))

@app.route('/selecionar_departamento/<path:nome_empresa>/<periodo>')
@login_required
def selecionar_departamento(nome_empresa, periodo):
    return render_template('selecionar_departamento.html', nome_empresa=nome_empresa, periodo=periodo)

@app.route('/dados/<path:nome_empresa>/<periodo>', methods=['GET', 'POST'])
@login_required
def dados_empresa(nome_empresa, periodo):
    dados_gerais = carregar_dados()
    if nome_empresa not in dados_gerais:
        flash('Empresa não encontrada.', 'danger')
        return redirect(url_for('index'))
    dados_empresa_especifica = dados_gerais[nome_empresa]
    if request.method == 'POST':
        periodos_empresa = dados_empresa_especifica.get('periodos', {})
        if periodo not in periodos_empresa: periodos_empresa[periodo] = {}
        dados_periodo = periodos_empresa[periodo]
        
        dados_periodo['faturamento'] = {campo: para_float(request.form.get(campo)) for campo in CAMPOS_FATURAMENTO}
        dados_periodo['despesas'] = {campo: para_float(request.form.get(campo)) for campo in CAMPOS_DESPESAS}
        dados_periodo['impostos_federal'] = {campo: para_float(request.form.get(campo)) for campo in CAMPOS_IMPOSTOS_FEDERAL}
        dados_periodo['impostos_estadual'] = {campo: para_float(request.form.get(campo)) for campo in CAMPOS_IMPOSTOS_ESTADUAL}
        dados_periodo['impostos_municipal'] = {campo: para_float(request.form.get(campo)) for campo in CAMPOS_IMPOSTOS_MUNICIPAL}
        dados_periodo['retencoes_federal'] = {campo: para_float(request.form.get(campo)) for campo in CAMPOS_RETENCOES_FEDERAL}
        
        dados_periodo['faturamento']['lancado'] = 'fat_lancado' in request.form
        dados_periodo['faturamento']['concluido'] = 'fat_concluido' in request.form
        dados_periodo['impostos_federal']['lancado'] = 'imp_fed_lancado' in request.form
        dados_periodo['impostos_federal']['concluido'] = 'imp_fed_concluido' in request.form
        dados_periodo['retencoes_federal']['lancado'] = 'ret_fed_lancado' in request.form
        dados_periodo['retencoes_federal']['concluido'] = 'ret_fed_concluido' in request.form

        dados_gerais[nome_empresa]['periodos'] = periodos_empresa
        salvar_dados(dados_gerais)
        flash(f'Dados para {nome_empresa} ({periodo}) salvos com sucesso!', 'success')
        return redirect(url_for('dados_empresa', nome_empresa=nome_empresa, periodo=periodo))
    
    dados_atuais_periodo = dados_empresa_especifica.get('periodos', {}).get(periodo, {})
    status_periodo = dados_atuais_periodo.get('status', 'Em Aberto')
    return render_template('dados_empresa.html', 
                           nome_empresa=nome_empresa, periodo=periodo,
                           dados_empresa=dados_empresa_especifica, dados=dados_atuais_periodo, status=status_periodo,
                           campos_faturamento=CAMPOS_FATURAMENTO, campos_despesas=CAMPOS_DESPESAS,
                           campos_impostos_federal=CAMPOS_IMPOSTOS_FEDERAL, campos_impostos_estadual=CAMPOS_IMPOSTOS_ESTADUAL,
                           campos_impostos_municipal=CAMPOS_IMPOSTOS_MUNICIPAL, campos_retencoes_federal=CAMPOS_RETENCOES_FEDERAL)

@app.route('/deactivated_companies')
@login_required
def deactivated_companies():
    dados = carregar_dados()
    empresas_inativas = {nome: detalhes for nome, detalhes in dados.items() if not detalhes.get('active', True)}
    empresas_ordenadas = dict(sorted(empresas_inativas.items()))
    return render_template('deactivated_companies.html', empresas=empresas_ordenadas)

@app.route('/deactivate_company/<path:nome_empresa>', methods=['POST'])
@login_required
def deactivate_company(nome_empresa):
    dados = carregar_dados()
    if nome_empresa in dados:
        dados[nome_empresa]['active'] = False
        salvar_dados(dados)
        flash(f'Empresa "{nome_empresa}" foi desativada.', 'warning')
    else:
        flash('Empresa não encontrada.', 'danger')
    return redirect(url_for('index'))

@app.route('/reactivate_company/<path:nome_empresa>', methods=['POST'])
@login_required
def reactivate_company(nome_empresa):
    dados = carregar_dados()
    if nome_empresa in dados:
        dados[nome_empresa]['active'] = True
        salvar_dados(dados)
        flash(f'Empresa "{nome_empresa}" foi reativada com sucesso.', 'success')
    else:
        flash('Empresa não encontrada.', 'danger')
    return redirect(url_for('deactivated_companies'))

@app.route('/delete_company_permanently/<path:nome_empresa>', methods=['POST'])
@login_required
def delete_company_permanently(nome_empresa):
    dados = carregar_dados()
    if nome_empresa in dados:
        del dados[nome_empresa]
        salvar_dados(dados)
        flash(f'Empresa "{nome_empresa}" foi excluída permanentemente.', 'success')
    else:
        flash('Empresa não encontrada.', 'danger')
    return redirect(url_for('deactivated_companies'))

@app.route('/finalize_month/<path:nome_empresa>/<periodo>', methods=['POST'])
@login_required
def finalize_month(nome_empresa, periodo):
    dados_gerais = carregar_dados()
    if nome_empresa in dados_gerais:
        if 'periodos' not in dados_gerais[nome_empresa]: dados_gerais[nome_empresa]['periodos'] = {}
        if periodo not in dados_gerais[nome_empresa]['periodos']: dados_gerais[nome_empresa]['periodos'][periodo] = {}
        dados_gerais[nome_empresa]['periodos'][periodo]['status'] = 'Finalizado'
        salvar_dados(dados_gerais)
        flash('Mês finalizado com sucesso!', 'success')
    else:
        flash('Erro ao finalizar o mês. Empresa não encontrada.', 'danger')
    return redirect(url_for('dados_empresa', nome_empresa=nome_empresa, periodo=periodo))

@app.route('/reopen_month/<path:nome_empresa>/<periodo>', methods=['POST'])
@login_required
def reopen_month(nome_empresa, periodo):
    dados_gerais = carregar_dados()
    if nome_empresa in dados_gerais and periodo in dados_gerais[nome_empresa].get('periodos', {}):
        dados_gerais[nome_empresa]['periodos'][periodo]['status'] = 'Em Aberto'
        salvar_dados(dados_gerais)
        flash('Mês reaberto para edição!', 'info')
    else:
        flash('Erro ao reabrir o mês.', 'danger')
    return redirect(url_for('dados_empresa', nome_empresa=nome_empresa, periodo=periodo))

@app.route('/export_xlsx')
@login_required
def export_xlsx():
    ano = request.args.get('ano')
    mes = request.args.get('mes')
    if not ano or not mes:
        flash('Por favor, selecione um mês e ano no painel "Gerenciar Dados Mensais" antes de exportar.', 'warning')
        return redirect(url_for('index'))
    periodo_alvo = f"{ano}-{mes}"
    dados = carregar_dados()
    filename = f"export_contajur_{periodo_alvo}.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = f"Dados {mes}-{ano}"
    
    headers = ['Empresa', 'CNPJ', 'Envio de Imposto', 'Prazo', 'Ano', 'Mes', 'Status', 
               'Faturamento Lançado', 'Faturamento Concluído', 
               'Imp. Federais Lançado', 'Imp. Federais Concluído',
               'Ret. Federais Lançado', 'Ret. Federais Concluído'] + \
              CAMPOS_FATURAMENTO + CAMPOS_DESPESAS + CAMPOS_IMPOSTOS_FEDERAL + CAMPOS_IMPOSTOS_ESTADUAL + CAMPOS_IMPOSTOS_MUNICIPAL + CAMPOS_RETENCOES_FEDERAL
    ws.append(headers)

    for nome_empresa, detalhes_empresa in dados.items():
        if not detalhes_empresa.get('active', True): continue
        periodos = detalhes_empresa.get('periodos', {})
        if periodo_alvo in periodos:
            categorias = periodos[periodo_alvo]
            fat = categorias.get('faturamento', {})
            imp_fed = categorias.get('impostos_federal', {})
            ret_fed = categorias.get('retencoes_federal', {})
            
            row_data = [
                nome_empresa, detalhes_empresa.get('cnpj', ''), detalhes_empresa.get('envio_imposto', ''),
                detalhes_empresa.get('prazo', ''), ano, mes, categorias.get('status', 'Em Aberto'),
                "Sim" if fat.get('lancado') else "Não", "Sim" if fat.get('concluido') else "Não",
                "Sim" if imp_fed.get('lancado') else "Não", "Sim" if imp_fed.get('concluido') else "Não",
                "Sim" if ret_fed.get('lancado') else "Não", "Sim" if ret_fed.get('concluido') else "Não",
            ]
            for campo in CAMPOS_FATURAMENTO: row_data.append(fat.get(campo, 0.0))
            for campo in CAMPOS_DESPESAS: row_data.append(categorias.get('despesas', {}).get(campo, 0.0))
            for campo in CAMPOS_IMPOSTOS_FEDERAL: row_data.append(imp_fed.get(campo, 0.0))
            for campo in CAMPOS_IMPOSTOS_ESTADUAL: row_data.append(categorias.get('impostos_estadual', {}).get(campo, 0.0))
            for campo in CAMPOS_IMPOSTOS_MUNICIPAL: row_data.append(categorias.get('impostos_municipal', {}).get(campo, 0.0))
            for campo in CAMPOS_RETENCOES_FEDERAL: row_data.append(ret_fed.get(campo, 0.0))
            ws.append(row_data)
            
    if ws.max_row <= 1:
        flash(f'Nenhum dado encontrado para o período {mes}/{ano} para ser exportado.', 'info')
        return redirect(url_for('index'))
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return Response(buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={"Content-Disposition": f"attachment;filename={filename}"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port)
