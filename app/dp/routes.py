# app/dp/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.utils import carregar_dados, salvar_dados, login_required
from app.pdf_parser import extrair_dados_pdf

dp_bp = Blueprint('dp', __name__)

@dp_bp.route('/upload_dp_page')
@login_required
def upload_dp_page():
    return render_template('upload_dp.html')

@dp_bp.route('/upload_dp', methods=['POST'])
@login_required
def upload_dp():
    pdf_files = request.files.getlist('pdf_files')
    if not pdf_files or pdf_files[0].filename == '':
        flash('Por favor, selecione pelo menos um arquivo PDF.', 'danger')
        return redirect(url_for('dp.upload_dp_page'))

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

    return redirect(url_for('dp.upload_dp_page'))

@dp_bp.route('/dados_dp/<path:nome_empresa>/<periodo>')
@login_required
def dados_dp(nome_empresa, periodo):
    dados = carregar_dados()
    dados_periodo = dados.get(nome_empresa, {}).get('periodos', {}).get(periodo, {})
    dados_dp = dados_periodo.get('departamento_pessoal')
    status_dp = dados_periodo.get('dp_status', 'Em Aberto')
    return render_template('dados_dp.html', nome_empresa=nome_empresa, periodo=periodo, dados_dp=dados_dp, status_dp=status_dp)

@dp_bp.route('/finalize_dp_month/<path:nome_empresa>/<periodo>', methods=['POST'])
@login_required
def finalize_dp_month(nome_empresa, periodo):
    dados = carregar_dados()
    if nome_empresa in dados and periodo in dados[nome_empresa].get('periodos', {}):
        dados[nome_empresa]['periodos'][periodo]['dp_status'] = 'Finalizado'
        salvar_dados(dados)
        flash('Mês do Departamento Pessoal finalizado com sucesso!', 'success')
    else:
        flash('Erro ao finalizar o mês.', 'danger')
    return redirect(url_for('dp.dados_dp', nome_empresa=nome_empresa, periodo=periodo))

@dp_bp.route('/reopen_dp_month/<path:nome_empresa>/<periodo>', methods=['POST'])
@login_required
def reopen_dp_month(nome_empresa, periodo):
    dados = carregar_dados()
    if nome_empresa in dados and periodo in dados[nome_empresa].get('periodos', {}):
        dados[nome_empresa]['periodos'][periodo]['dp_status'] = 'Em Aberto'
        salvar_dados(dados)
        flash('Mês do Departamento Pessoal reaberto para edição!', 'info')
    else:
        flash('Erro ao reabrir o mês.', 'danger')
    return redirect(url_for('dp.dados_dp', nome_empresa=nome_empresa, periodo=periodo))
