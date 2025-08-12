import os
import json
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
import io
from openpyxl import Workbook
from io import BytesIO
import pdfplumber
import re

# --- Configuração da Aplicação Flask ---
app = Flask(__name__)
app.secret_key = 'uma-chave-secreta-muito-dificil-de-adivinhar'

# --- Constantes e Configurações ---
NOME_ARQUIVO_DADOS = 'dados_empresas.json'
USUARIO_PADRAO = 'admin'
SENHA_PADRAO = 'contajur2025'

# --- Listas de Campos ---
CAMPOS_FATURAMENTO = [
    "Serviços tributados", "Serviços retidos", "Venda (indústria/imóveis)",
    "Revenda mercadorias tributárias", "Revenda mercadorias não tributárias",
    "Revenda de mercadoria monofásica", "Locação", "Receita sem nota fiscal"
]
CAMPOS_DESPESAS = [
    "Compras para revenda", "Compras para uso/consumo",
    "Compras para ativo imobilizado", "Serviços tomados com nota fiscal"
]
CAMPOS_IMPOSTOS_FEDERAL = ["Simples", "PIS", "COFINS", "IRPJ", "CSLL", "IOF", "IPI"]
CAMPOS_IMPOSTOS_ESTADUAL = ["ICMS próprio", "ICMS ST próprio", "DIFAL", "Antecipação", "ICMS ST Entradas", "FEM"]
CAMPOS_IMPOSTOS_MUNICIPAL = ["ISSQN a pagar", "ISSQN Retido (NF própria)"]
CAMPOS_RETENCOES_FEDERAL = ["CSRF (Retido)", "IRRF (Retido)", "INSS (Retido)", "ISSQN (Retido)"]

# --- FUNÇÃO DE EXTRAÇÃO DE PDF (ADAPTADA) ---
def extrair_dados_pdf(pdf_file_stream):
    texto_completo = ""
    try:
        with pdfplumber.open(pdf_file_stream) as pdf:
            for pagina in pdf.pages:
                texto_da_pagina = pagina.extract_text(x_tolerance=2, y_tolerance=2)
                if texto_da_pagina:
                    texto_completo += texto_da_pagina + "\n"
    except Exception as e:
        return {"erro": f"Não foi possível ler o arquivo PDF: {e}"}

    dados = {
        "CNPJ": None, "PERIODO": None, "SITUACAO_COLABORADORES": None, "COLABORADORES": [],
        "LIQUIDO_COLABORADORES": None, "LIQUIDO_EMPREGADORES": None, "VALOR_GPS": None,
        "VALOR_GFD_MENSAL": None, "VALOR_GFD_RESCISORIA": None
    }
    
    mapa_meses = {"JANEIRO": "01", "FEVEREIRO": "02", "MARÇO": "03", "ABRIL": "04", "MAIO": "05", "JUNHO": "06", "JULHO": "07", "AGOSTO": "08", "SETEMBRO": "09", "OUTUBRO": "10", "NOVEMBRO": "11", "DEZEMBRO": "12"}
    match_periodo = re.search(r"referente ao mês de (\w+)/(\d{4})", texto_completo, re.IGNORECASE)
    if match_periodo:
        mes_nome = match_periodo.group(1).upper()
        ano = match_periodo.group(2)
        mes_num = mapa_meses.get(mes_nome)
        if mes_num: dados["PERIODO"] = f"{ano}-{mes_num}"

    linhas = texto_completo.split('\n')
    for i, linha in enumerate(linhas):
        if "Admissão em" in linha:
            partes = linha.split("Admissão em")
            nome_limpo = re.sub(r'^\d+\s+', '', partes[0]).strip()
            nome_limpo = re.sub(r'\s+[\d\s]+$', '', nome_limpo).strip()
            match_data = re.search(r'(\d{2}/\d{2}/\d{4})', partes[1])
            if nome_limpo and match_data:
                data_admissao = match_data.group(1)
                proxima_linha = linhas[i + 1] if i + 1 < len(linhas) else ""
                if len(proxima_linha.strip().split()) <= 3 and proxima_linha and "Pró-Labore" not in proxima_linha:
                    nome_limpo = f"{nome_limpo} {proxima_linha.strip()}"
                    contexto_seguinte = "\n".join(linhas[i + 2:min(i + 12, len(linhas))])
                else:
                    contexto_seguinte = "\n".join(linhas[i + 1:min(i + 11, len(linhas))])
                if "Pró-Labore" not in contexto_seguinte:
                    dados["COLABORADORES"].append({"nome": nome_limpo, "admissao": data_admissao})

    match_cnpj = re.search(r"CNPJ:(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", texto_completo)
    if match_cnpj: dados["CNPJ"] = match_cnpj.group(1).strip()
    match_situacao = re.search(r"Ativos: \d+.*(?:Doença|Outras sit\.): \d+", texto_completo)
    if match_situacao: dados["SITUACAO_COLABORADORES"] = match_situacao.group(0).strip()
    
    match_liquido = re.search(r"^L[íi]quido\s+[\d\.,]+\s+([\d\.,]+)\s+([\d\.,]+)", texto_completo, re.MULTILINE | re.IGNORECASE)
    if match_liquido:
        dados["LIQUIDO_COLABORADORES"] = match_liquido.group(1).strip()
        dados["LIQUIDO_EMPREGADORES"] = match_liquido.group(2).strip()

    impostos_encontrados = {}
    for match in re.finditer(r"^(GPS|GFD Mensal|GFD Rescisória)\s+R\$\s+([\d\.,]+)", texto_completo, re.MULTILINE):
        impostos_encontrados[match.group(1).strip()] = f"R$ {match.group(2).strip()}"
    dados["VALOR_GPS"] = impostos_encontrados.get("GPS", "Não encontrado")
    dados["VALOR_GFD_MENSAL"] = impostos_encontrados.get("GFD Mensal", "Não encontrado")
    dados["VALOR_GFD_RESCISORIA"] = impostos_encontrados.get("GFD Rescisória", "Não encontrado")
    
    return dados

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
    
    now = datetime.now()
    search_ano = request.args.get('search_ano', str(now.year))
    search_mes = request.args.get('search_mes', f"{now.month:02d}")
    search_status = request.args.get('search_status')
    
    periodo_pesquisado = f"{search_ano}-{search_mes}"
    
    empresas_fiscal_em_aberto = []
    empresas_fiscal_finalizadas = []
    empresas_dp_em_aberto = []
    empresas_dp_finalizadas = []
    empresas_resultado_filtro = None
    status_pesquisado_label = None

    for nome, detalhes in empresas_ordenadas.items():
        dados_periodo = detalhes.get('periodos', {}).get(periodo_pesquisado, {})
        if dados_periodo.get('status') == 'Finalizado':
            empresas_fiscal_finalizadas.append(nome)
        else:
            empresas_fiscal_em_aberto.append(nome)
        if dados_periodo.get('dp_status') == 'Finalizado':
            empresas_dp_finalizadas.append(nome)
        else:
            empresas_dp_em_aberto.append(nome)

    if search_status:
        empresas_resultado_filtro = []
        status_labels = { "fiscal_em_aberto": "Fiscal - Em Aberto", "fiscal_finalizado": "Fiscal - Finalizado", "dp_em_aberto": "Dep. Pessoal - Em Aberto", "dp_finalizado": "Dep. Pessoal - Finalizado" }
        status_pesquisado_label = status_labels.get(search_status)
        
        if search_status == 'fiscal_em_aberto': empresas_resultado_filtro = empresas_fiscal_em_aberto
        elif search_status == 'fiscal_finalizado': empresas_resultado_filtro = empresas_fiscal_finalizadas
        elif search_status == 'dp_em_aberto': empresas_resultado_filtro = empresas_dp_em_aberto
        elif search_status == 'dp_finalizado': empresas_resultado_filtro = empresas_dp_finalizadas

    meses = [f"{i:02d}" for i in range(1, 13)]
    anos = [str(i) for i in range(2010, now.year + 6)]
    
    return render_template('index.html', 
                           empresas=empresas_ordenadas, meses=meses, anos=anos, 
                           ano_atual=str(now.year), mes_atual=f"{now.month:02d}",
                           empresas_resultado_filtro=empresas_resultado_filtro,
                           empresas_fiscal_em_aberto=empresas_fiscal_em_aberto,
                           empresas_fiscal_finalizadas=empresas_fiscal_finalizadas,
                           empresas_dp_em_aberto=empresas_dp_em_aberto,
                           empresas_dp_finalizadas=empresas_dp_finalizadas,
                           periodo_pesquisado=periodo_pesquisado,
                           search_ano=search_ano, search_mes=search_mes,
                           search_status=search_status, 
                           filtro_label=status_pesquisado_label)

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
    dados = carregar_dados()
    return render_template('selecionar_departamento.html', nome_empresa=nome_empresa, periodo=periodo, dados=dados)

@app.route('/dashboard_fiscal/<path:nome_empresa>/<periodo>')
@login_required
def dashboard_fiscal(nome_empresa, periodo):
    dados = carregar_dados()
    dados_periodo = dados.get(nome_empresa, {}).get('periodos', {}).get(periodo, {})
    
    def prepare_chart_data(data_dict):
        chart_data = {k: v for k, v in data_dict.items() if isinstance(v, (int, float)) and v > 0}
        return { "labels": list(chart_data.keys()), "data": list(chart_data.values()) }

    chart_faturamento = prepare_chart_data(dados_periodo.get('faturamento', {}))
    chart_despesas = prepare_chart_data(dados_periodo.get('despesas', {}))
    chart_imp_federal = prepare_chart_data(dados_periodo.get('impostos_federal', {}))
    chart_imp_estadual = prepare_chart_data(dados_periodo.get('impostos_estadual', {}))
    chart_imp_municipal = prepare_chart_data(dados_periodo.get('impostos_municipal', {}))
    chart_ret_federal = prepare_chart_data(dados_periodo.get('retencoes_federal', {}))

    return render_template('dashboard_fiscal.html', 
                           nome_empresa=nome_empresa, periodo=periodo,
                           chart_faturamento=chart_faturamento,
                           chart_despesas=chart_despesas,
                           chart_imp_federal=chart_imp_federal,
                           chart_imp_estadual=chart_imp_estadual,
                           chart_imp_municipal=chart_imp_municipal,
                           chart_ret_federal=chart_ret_federal)

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
        dados_periodo['impostos_estadual']['lancado'] = 'imp_est_lancado' in request.form
        dados_periodo['impostos_estadual']['concluido'] = 'imp_est_concluido' in request.form
        dados_periodo['impostos_municipal']['lancado'] = 'imp_mun_lancado' in request.form
        dados_periodo['impostos_municipal']['concluido'] = 'imp_mun_concluido' in request.form
        dados_periodo['retencoes_federal']['lancado'] = 'ret_fed_lancado' in request.form
        dados_periodo['retencoes_federal']['concluido'] = 'ret_fed_concluido' in request.form
        dados_periodo['retencoes_federal']['sem_notas'] = 'ret_fed_sem_notas' in request.form
        dados_periodo['retencoes_federal']['dispensado'] = 'ret_fed_dispensado' in request.form

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

@app.route('/upload_dp_page')
@login_required
def upload_dp_page():
    return render_template('upload_dp.html')

@app.route('/upload_dp', methods=['POST'])
@login_required
def upload_dp():
    pdf_files = request.files.getlist('pdf_files')
    if not pdf_files or pdf_files[0].filename == '':
        flash('Por favor, selecione pelo menos um arquivo PDF.', 'danger')
        return redirect(url_for('upload_dp_page'))

    dados_gerais = carregar_dados()
    cnpj_map = {detalhes.get('cnpj'): nome for nome, detalhes in dados_gerais.items() if detalhes.get('cnpj')}
    
    sucesso_count = 0
    falha_cnpj = []
    falha_leitura = []
    falha_periodo = []

    for file in pdf_files:
        if file.filename == '': continue
        try:
            dados_extraidos = extrair_dados_pdf(file.stream)
            if "erro" in dados_extraidos:
                falha_leitura.append(file.filename)
                continue

            cnpj_extraido = dados_extraidos.get("CNPJ")
            periodo_extraido = dados_extraidos.get("PERIODO")

            if not periodo_extraido:
                falha_periodo.append(file.filename)
                continue
            
            if cnpj_extraido and cnpj_extraido in cnpj_map:
                nome_empresa = cnpj_map[cnpj_extraido]
                if 'periodos' not in dados_gerais[nome_empresa]: dados_gerais[nome_empresa]['periodos'] = {}
                if periodo_extraido not in dados_gerais[nome_empresa]['periodos']: dados_gerais[nome_empresa]['periodos'][periodo_extraido] = {}
                
                dados_gerais[nome_empresa]['periodos'][periodo_extraido]['departamento_pessoal'] = dados_extraidos
                sucesso_count += 1
            else:
                falha_cnpj.append(file.filename)
        except Exception:
            falha_leitura.append(file.filename)

    salvar_dados(dados_gerais)
    
    if sucesso_count > 0: flash(f'{sucesso_count} arquivos processados e salvos com sucesso!', 'success')
    if falha_cnpj: flash(f'Falha ao encontrar o CNPJ no sistema para os arquivos: {", ".join(falha_cnpj)}', 'warning')
    if falha_periodo: flash(f'Não foi possível identificar o período nos arquivos: {", ".join(falha_periodo)}', 'warning')
    if falha_leitura: flash(f'Falha ao ler os seguintes arquivos PDF: {", ".join(falha_leitura)}', 'danger')

    return redirect(url_for('upload_dp_page'))

@app.route('/dados_dp/<path:nome_empresa>/<periodo>')
@login_required
def dados_dp(nome_empresa, periodo):
    dados = carregar_dados()
    dados_periodo = dados.get(nome_empresa, {}).get('periodos', {}).get(periodo, {})
    dados_dp = dados_periodo.get('departamento_pessoal')
    status_dp = dados_periodo.get('dp_status', 'Em Aberto')
    return render_template('dados_dp.html', nome_empresa=nome_empresa, periodo=periodo, dados_dp=dados_dp, status_dp=status_dp)

@app.route('/finalize_dp_month/<path:nome_empresa>/<periodo>', methods=['POST'])
@login_required
def finalize_dp_month(nome_empresa, periodo):
    dados = carregar_dados()
    if nome_empresa in dados and periodo in dados[nome_empresa].get('periodos', {}):
        dados[nome_empresa]['periodos'][periodo]['dp_status'] = 'Finalizado'
        salvar_dados(dados)
        flash('Mês do Departamento Pessoal finalizado com sucesso!', 'success')
    else:
        flash('Erro ao finalizar o mês.', 'danger')
    return redirect(url_for('dados_dp', nome_empresa=nome_empresa, periodo=periodo))

@app.route('/reopen_dp_month/<path:nome_empresa>/<periodo>', methods=['POST'])
@login_required
def reopen_dp_month(nome_empresa, periodo):
    dados = carregar_dados()
    if nome_empresa in dados and periodo in dados[nome_empresa].get('periodos', {}):
        dados[nome_empresa]['periodos'][periodo]['dp_status'] = 'Em Aberto'
        salvar_dados(dados)
        flash('Mês do Departamento Pessoal reaberto para edição!', 'info')
    else:
        flash('Erro ao reabrir o mês.', 'danger')
    return redirect(url_for('dados_dp', nome_empresa=nome_empresa, periodo=periodo))

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
               'Imp. Estaduais Lançado', 'Imp. Estaduais Concluído',
               'Imp. Municipais Lançado', 'Imp. Municipais Concluído',
               'Ret. Federais Lançado', 'Ret. Federais Concluído',
               'Ret. Federais Sem Notas', 'Ret. Federais Dispensado'] + \
              CAMPOS_FATURAMENTO + CAMPOS_DESPESAS + CAMPOS_IMPOSTOS_FEDERAL + CAMPOS_IMPOSTOS_ESTADUAL + CAMPOS_IMPOSTOS_MUNICIPAL + CAMPOS_RETENCOES_FEDERAL
    ws.append(headers)

    for nome_empresa, detalhes_empresa in dados.items():
        if not detalhes_empresa.get('active', True): continue
        periodos = detalhes_empresa.get('periodos', {})
        if periodo_alvo in periodos:
            categorias = periodos[periodo_alvo]
            fat = categorias.get('faturamento', {})
            imp_fed = categorias.get('impostos_federal', {})
            imp_est = categorias.get('impostos_estadual', {})
            imp_mun = categorias.get('impostos_municipal', {})
            ret_fed = categorias.get('retencoes_federal', {})
            
            row_data = [
                nome_empresa, detalhes_empresa.get('cnpj', ''), detalhes_empresa.get('envio_imposto', ''),
                detalhes_empresa.get('prazo', ''), ano, mes, categorias.get('status', 'Em Aberto'),
                "Sim" if fat.get('lancado') else "Não", "Sim" if fat.get('concluido') else "Não",
                "Sim" if imp_fed.get('lancado') else "Não", "Sim" if imp_fed.get('concluido') else "Não",
                "Sim" if imp_est.get('lancado') else "Não", "Sim" if imp_est.get('concluido') else "Não",
                "Sim" if imp_mun.get('lancado') else "Não", "Sim" if imp_mun.get('concluido') else "Não",
                "Sim" if ret_fed.get('lancado') else "Não", "Sim" if ret_fed.get('concluido') else "Não",
                "Sim" if ret_fed.get('sem_notas') else "Não", "Sim" if ret_fed.get('dispensado') else "Não",
            ]
            for campo in CAMPOS_FATURAMENTO: row_data.append(fat.get(campo, 0.0))
            for campo in CAMPOS_DESPESAS: row_data.append(categorias.get('despesas', {}).get(campo, 0.0))
            for campo in CAMPOS_IMPOSTOS_FEDERAL: row_data.append(imp_fed.get(campo, 0.0))
            for campo in CAMPOS_IMPOSTOS_ESTADUAL: row_data.append(imp_est.get(campo, 0.0))
            for campo in CAMPOS_IMPOSTOS_MUNICIPAL: row_data.append(imp_mun.get(campo, 0.0))
            for campo in CAMPOS_RETENCOES_FEDERAL: row_data.append(ret_fed.get(campo, 0.0))
            ws.append(row_data)
            
    if ws.max_row <= 1:
        flash(f'Nenhum dado encontrado para o período {mes}/{ano} para ser exportado.', 'info')
        return redirect(url_for('index'))
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return Response(buffer, mimetype='application/vnd.openxmlformats-officedocument.sheet', headers={"Content-Disposition": f"attachment;filename={filename}"})