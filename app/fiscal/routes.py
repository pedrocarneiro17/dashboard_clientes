# app/fiscal/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from app import db, Empresa, Periodo # Importa o db e os Modelos do __init__.py
from app.utils import para_float, login_required
from app.config import *
from openpyxl import Workbook
from io import BytesIO

fiscal_bp = Blueprint('fiscal', __name__)

# --- FUNÇÃO AUXILIAR PARA SALVAR DADOS NO BANCO DE DADOS ---
def _save_fiscal_data(nome_empresa, periodo_str, form_data):
    """Encontra ou cria um período e salva os dados fiscais no banco de dados."""
    empresa = Empresa.query.filter_by(nome=nome_empresa).first()
    if not empresa:
        return False

    # Procura pelo período; se não existir, cria um novo
    periodo_obj = Periodo.query.filter_by(empresa_id=empresa.id, ano_mes=periodo_str).first()
    if not periodo_obj:
        periodo_obj = Periodo(ano_mes=periodo_str, empresa_id=empresa.id)
        db.session.add(periodo_obj)

    # Prepara o dicionário com os dados fiscais a partir do formulário
    dados_fiscais_json = {
        'faturamento': {campo: para_float(form_data.get(campo)) for campo in CAMPOS_FATURAMENTO},
        'despesas': {campo: para_float(form_data.get(campo)) for campo in CAMPOS_DESPESAS},
        'impostos_federal': {campo: para_float(form_data.get(campo)) for campo in CAMPOS_IMPOSTOS_FEDERAL},
        'impostos_estadual': {campo: para_float(form_data.get(campo)) for campo in CAMPOS_IMPOSTOS_ESTADUAL},
        'impostos_municipal': {campo: para_float(form_data.get(campo)) for campo in CAMPOS_IMPOSTOS_MUNICIPAL},
        'retencoes_federal': {campo: para_float(form_data.get(campo)) for campo in CAMPOS_RETENCOES_FEDERAL}
    }
    
    # Adiciona o estado dos checkboxes
    dados_fiscais_json['faturamento']['lancado'] = 'fat_lancado' in form_data
    dados_fiscais_json['faturamento']['concluido'] = 'fat_concluido' in form_data
    dados_fiscais_json['impostos_federal']['lancado'] = 'imp_fed_lancado' in form_data
    dados_fiscais_json['impostos_federal']['concluido'] = 'imp_fed_concluido' in form_data
    dados_fiscais_json['impostos_estadual']['lancado'] = 'imp_est_lancado' in form_data
    dados_fiscais_json['impostos_estadual']['concluido'] = 'imp_est_concluido' in form_data
    dados_fiscais_json['impostos_municipal']['lancado'] = 'imp_mun_lancado' in form_data
    dados_fiscais_json['impostos_municipal']['concluido'] = 'imp_mun_concluido' in form_data
    dados_fiscais_json['retencoes_federal']['lancado'] = 'ret_fed_lancado' in form_data
    dados_fiscais_json['retencoes_federal']['concluido'] = 'ret_fed_concluido' in form_data
    dados_fiscais_json['retencoes_federal']['sem_notas'] = 'ret_fed_sem_notas' in form_data
    dados_fiscais_json['retencoes_federal']['dispensado'] = 'ret_fed_dispensado' in form_data

    # Atribui o dicionário JSON ao campo do período e salva
    periodo_obj.dados_fiscais = dados_fiscais_json
    db.session.commit()
    return True

@fiscal_bp.route('/selecionar_departamento/<path:nome_empresa>/<periodo>')
@login_required
def selecionar_departamento(nome_empresa, periodo):
    # A lógica para buscar status agora precisará consultar o DB
    empresa = Empresa.query.filter_by(nome=nome_empresa).first()
    dados_para_template = {}
    if empresa:
        periodo_obj = Periodo.query.filter_by(empresa_id=empresa.id, ano_mes=periodo).first()
        if periodo_obj:
            dados_para_template = {
                nome_empresa: {
                    "periodos": {
                        periodo: {
                            "status": periodo_obj.status,
                            "dp_status": periodo_obj.dp_status
                        }
                    }
                }
            }
    return render_template('selecionar_departamento.html', nome_empresa=nome_empresa, periodo=periodo, dados=dados_para_template)

@fiscal_bp.route('/dados/<path:nome_empresa>/<periodo>', methods=['GET', 'POST'])
@login_required
def dados_empresa(nome_empresa, periodo):
    empresa = Empresa.query.filter_by(nome=nome_empresa).first_or_404()
    
    if request.method == 'POST':
        if _save_fiscal_data(nome_empresa, periodo, request.form):
            flash(f'Dados para {nome_empresa} ({periodo}) salvos com sucesso!', 'success')
        else:
            flash('Erro ao salvar os dados.', 'danger')
        return redirect(url_for('fiscal.dados_empresa', nome_empresa=nome_empresa, periodo=periodo))
    
    # Busca o período no banco de dados
    periodo_obj = Periodo.query.filter_by(empresa_id=empresa.id, ano_mes=periodo).first()
    
    dados_atuais_periodo = periodo_obj.dados_fiscais if periodo_obj and periodo_obj.dados_fiscais else {}
    status_periodo = periodo_obj.status if periodo_obj else 'Em Aberto'
    
    return render_template('dados_empresa.html', 
                           nome_empresa=nome_empresa, periodo=periodo,
                           dados_empresa=empresa, dados=dados_atuais_periodo, status=status_periodo,
                           campos_faturamento=CAMPOS_FATURAMENTO, campos_despesas=CAMPOS_DESPESAS,
                           campos_impostos_federal=CAMPOS_IMPOSTOS_FEDERAL, campos_impostos_estadual=CAMPOS_IMPOSTOS_ESTADUAL,
                           campos_impostos_municipal=CAMPOS_IMPOSTOS_MUNICIPAL, campos_retencoes_federal=CAMPOS_RETENCOES_FEDERAL)

@fiscal_bp.route('/finalize_month/<path:nome_empresa>/<periodo>', methods=['POST'])
@login_required
def finalize_month(nome_empresa, periodo):
    _save_fiscal_data(nome_empresa, periodo, request.form)
    
    empresa = Empresa.query.filter_by(nome=nome_empresa).first_or_404()
    periodo_obj = Periodo.query.filter_by(empresa_id=empresa.id, ano_mes=periodo).first()
    if periodo_obj:
        periodo_obj.status = 'Finalizado'
        db.session.commit()
        flash('Mês finalizado com sucesso!', 'success')
    else:
        # Se o período não existir, a função _save_fiscal_data já o criou
        # então podemos buscar novamente e finalizar.
        periodo_obj = Periodo.query.filter_by(empresa_id=empresa.id, ano_mes=periodo).first()
        if periodo_obj:
            periodo_obj.status = 'Finalizado'
            db.session.commit()
            flash('Mês finalizado com sucesso!', 'success')
        else:
            flash('Erro: Período não encontrado para finalizar.', 'danger')
        
    return redirect(url_for('fiscal.dados_empresa', nome_empresa=nome_empresa, periodo=periodo))

@fiscal_bp.route('/reopen_month/<path:nome_empresa>/<periodo>', methods=['POST'])
@login_required
def reopen_month(nome_empresa, periodo):
    # Esta função agora SÓ altera o status, sem salvar os dados
    empresa = Empresa.query.filter_by(nome=nome_empresa).first_or_404()
    periodo_obj = Periodo.query.filter_by(empresa_id=empresa.id, ano_mes=periodo).first()
    if periodo_obj:
        periodo_obj.status = 'Em Aberto'
        db.session.commit()
        flash('Mês reaberto para edição!', 'info')
    else:
        flash('Erro ao reabrir o mês.', 'danger')
        
    return redirect(url_for('fiscal.dados_empresa', nome_empresa=nome_empresa, periodo=periodo))

@fiscal_bp.route('/export_xlsx')
@login_required
def export_xlsx():
    ano = request.args.get('ano')
    mes = request.args.get('mes')
    if not ano or not mes:
        flash('Por favor, selecione um mês e ano no painel "Gerenciar Dados Mensais" antes de exportar.', 'warning')
        return redirect(url_for('main.index'))
    periodo_alvo = f"{ano}-{mes}"
    
    # Busca os períodos relevantes do banco de dados
    periodos = Periodo.query.filter(Periodo.ano_mes == periodo_alvo, Periodo.empresa.has(active=True)).all()
    
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

    for periodo_obj in periodos:
        empresa = periodo_obj.empresa
        categorias = periodo_obj.dados_fiscais or {}
        fat = categorias.get('faturamento', {})
        imp_fed = categorias.get('impostos_federal', {})
        imp_est = categorias.get('impostos_estadual', {})
        imp_mun = categorias.get('impostos_municipal', {})
        ret_fed = categorias.get('retencoes_federal', {})
        
        row_data = [
            empresa.nome, empresa.cnpj, empresa.envio_imposto, empresa.prazo,
            ano, mes, periodo_obj.status,
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
        return redirect(url_for('main.index'))
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return Response(buffer, mimetype='application/vnd.openxmlformats-officedocument.sheet', headers={"Content-Disposition": f"attachment;filename={filename}"})