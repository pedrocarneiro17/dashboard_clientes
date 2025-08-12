# app/company/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.utils import carregar_dados, salvar_dados, login_required

company_bp = Blueprint('company', __name__)

@company_bp.route('/add_company_page')
@login_required
def add_company_page():
    return render_template('add_company.html')

@company_bp.route('/add_company', methods=['POST'])
@login_required
def add_company():
    nome_empresa = request.form.get('nome_empresa')
    if not nome_empresa:
        flash('O nome da empresa não pode ser vazio.', 'danger')
        return redirect(url_for('company.add_company_page'))
    dados = carregar_dados()
    if nome_empresa in dados:
        flash('Essa empresa já está cadastrada.', 'warning')
        return redirect(url_for('company.add_company_page'))
    
    dados[nome_empresa] = {
        'cnpj': request.form.get('cnpj', ''),
        'envio_imposto': request.form.get('envio_imposto', ''),
        'prazo': request.form.get('prazo', ''),
        'active': True,
        'periodos': {}
    }
    salvar_dados(dados)
    flash(f'Empresa "{nome_empresa}" adicionada com sucesso!', 'success')
    return redirect(url_for('main.index'))

@company_bp.route('/select_company_to_edit_page')
@login_required
def select_company_to_edit_page():
    dados = carregar_dados()
    empresas_ativas = {nome: detalhes for nome, detalhes in dados.items() if detalhes.get('active', True)}
    empresas_ordenadas = dict(sorted(empresas_ativas.items()))
    return render_template('select_company_to_edit.html', empresas=empresas_ordenadas)

@company_bp.route('/edit_company_page/<path:nome_empresa>')
@login_required
def edit_company_page(nome_empresa):
    dados = carregar_dados()
    empresa = dados.get(nome_empresa)
    if not empresa:
        flash('Empresa não encontrada.', 'danger')
        return redirect(url_for('main.index'))
    return render_template('edit_company.html', nome_empresa=nome_empresa, empresa=empresa)

@company_bp.route('/update_company/<path:nome_empresa>', methods=['POST'])
@login_required
def update_company(nome_empresa):
    dados = carregar_dados()
    if nome_empresa not in dados:
        flash('Empresa não encontrada.', 'danger')
        return redirect(url_for('main.index'))
    
    dados[nome_empresa]['cnpj'] = request.form.get('cnpj', '')
    dados[nome_empresa]['envio_imposto'] = request.form.get('envio_imposto', '')
    dados[nome_empresa]['prazo'] = request.form.get('prazo', '')
    
    salvar_dados(dados)
    flash(f'Dados da empresa "{nome_empresa}" atualizados com sucesso!', 'success')
    return redirect(url_for('main.index'))

@company_bp.route('/deactivated_companies')
@login_required
def deactivated_companies():
    dados = carregar_dados()
    empresas_inativas = {nome: detalhes for nome, detalhes in dados.items() if not detalhes.get('active', True)}
    empresas_ordenadas = dict(sorted(empresas_inativas.items()))
    return render_template('deactivated_companies.html', empresas=empresas_ordenadas)

@company_bp.route('/deactivate_company/<path:nome_empresa>', methods=['POST'])
@login_required
def deactivate_company(nome_empresa):
    dados = carregar_dados()
    if nome_empresa in dados:
        dados[nome_empresa]['active'] = False
        salvar_dados(dados)
        flash(f'Empresa "{nome_empresa}" foi desativada.', 'warning')
    else:
        flash('Empresa não encontrada.', 'danger')
    return redirect(url_for('main.index'))

@company_bp.route('/reactivate_company/<path:nome_empresa>', methods=['POST'])
@login_required
def reactivate_company(nome_empresa):
    dados = carregar_dados()
    if nome_empresa in dados:
        dados[nome_empresa]['active'] = True
        salvar_dados(dados)
        flash(f'Empresa "{nome_empresa}" foi reativada com sucesso.', 'success')
    else:
        flash('Empresa não encontrada.', 'danger')
    return redirect(url_for('company.deactivated_companies'))

@company_bp.route('/delete_company_permanently/<path:nome_empresa>', methods=['POST'])
@login_required
def delete_company_permanently(nome_empresa):
    dados = carregar_dados()
    if nome_empresa in dados:
        del dados[nome_empresa]
        salvar_dados(dados)
        flash(f'Empresa "{nome_empresa}" foi excluída permanentemente.', 'success')
    else:
        flash('Empresa não encontrada.', 'danger')
    return redirect(url_for('company.deactivated_companies'))
