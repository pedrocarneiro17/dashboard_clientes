# app/company/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db, Empresa # Importa o db e o modelo Empresa
from app.utils import login_required

company_bp = Blueprint('company', __name__)

@company_bp.route('/add_company_page')
@login_required
def add_company_page():
    """Mostra a página para adicionar uma nova empresa."""
    return render_template('add_company.html')

@company_bp.route('/add_company', methods=['POST'])
@login_required
def add_company():
    """Processa o formulário para adicionar uma nova empresa ao banco de dados."""
    nome = request.form.get('nome_empresa')
    cnpj = request.form.get('cnpj')
    envio_imposto = request.form.get('envio_imposto')
    prazo = request.form.get('prazo')

    # Verifica se já existe uma empresa com o mesmo nome
    empresa_existente = Empresa.query.filter_by(nome=nome).first()
    if empresa_existente:
        flash(f'Já existe uma empresa cadastrada com o nome "{nome}".', 'warning')
        return redirect(url_for('company.add_company_page'))

    # Cria uma nova instância do modelo Empresa e adiciona ao banco
    nova_empresa = Empresa(
        nome=nome,
        cnpj=cnpj,
        envio_imposto=envio_imposto,
        prazo=prazo
    )
    db.session.add(nova_empresa)
    db.session.commit()
    
    flash(f'Empresa "{nome}" cadastrada com sucesso!', 'success')
    return redirect(url_for('main.index'))

@company_bp.route('/select_company_to_edit_page')
@login_required
def select_company_to_edit_page():
    """Mostra a página para selecionar qual empresa editar."""
    empresas_ativas = Empresa.query.filter_by(active=True).order_by(Empresa.nome).all()
    return render_template('select_company_to_edit.html', empresas=empresas_ativas)

@company_bp.route('/edit_company_page/<path:nome_empresa>')
@login_required
def edit_company_page(nome_empresa):
    """Mostra o formulário de edição para uma empresa específica."""
    empresa = Empresa.query.filter_by(nome=nome_empresa).first_or_404()
    return render_template('edit_company.html', nome_empresa=empresa.nome, empresa=empresa)

@company_bp.route('/update_company/<path:nome_empresa>', methods=['POST'])
@login_required
def update_company(nome_empresa):
    """Atualiza os dados de uma empresa no banco de dados."""
    empresa = Empresa.query.filter_by(nome=nome_empresa).first_or_404()
    
    empresa.cnpj = request.form.get('cnpj')
    empresa.envio_imposto = request.form.get('envio_imposto')
    empresa.prazo = request.form.get('prazo')
    
    db.session.commit()
    flash(f'Dados da empresa "{empresa.nome}" atualizados com sucesso!', 'success')
    return redirect(url_for('main.index'))

@company_bp.route('/deactivate_company/<path:nome_empresa>', methods=['POST'])
@login_required
def deactivate_company(nome_empresa):
    """Marca uma empresa como inativa."""
    empresa = Empresa.query.filter_by(nome=nome_empresa).first_or_404()
    empresa.active = False
    db.session.commit()
    flash(f'Empresa "{empresa.nome}" foi desativada.', 'info')
    return redirect(url_for('main.index'))

@company_bp.route('/deactivated_companies')
@login_required
def deactivated_companies():
    """Mostra a lista de empresas desativadas."""
    empresas_inativas = Empresa.query.filter_by(active=False).order_by(Empresa.nome).all()
    return render_template('deactivated_companies.html', empresas=empresas_inativas)

@company_bp.route('/reactivate_company/<path:nome_empresa>', methods=['POST'])
@login_required
def reactivate_company(nome_empresa):
    """Reativa uma empresa."""
    empresa = Empresa.query.filter_by(nome=nome_empresa).first_or_404()
    empresa.active = True
    db.session.commit()
    flash(f'Empresa "{empresa.nome}" foi reativada com sucesso!', 'success')
    return redirect(url_for('company.deactivated_companies'))

@company_bp.route('/delete_company_permanently/<path:nome_empresa>', methods=['POST'])
@login_required
def delete_company_permanently(nome_empresa):
    """Exclui permanentemente uma empresa e todos os seus dados."""
    empresa = Empresa.query.filter_by(nome=nome_empresa).first_or_404()
    db.session.delete(empresa)
    db.session.commit()
    flash(f'Empresa "{empresa.nome}" e todos os seus dados foram excluídos permanentemente.', 'danger')
    return redirect(url_for('company.deactivated_companies'))