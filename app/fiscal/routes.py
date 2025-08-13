# app/fiscal/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from app.utils import carregar_dados, salvar_dados, para_float, login_required
from app.config import *
from openpyxl import Workbook
from io import BytesIO

fiscal_bp = Blueprint('fiscal', __name__)

# --- FUNÇÃO AUXILIAR PARA SALVAR DADOS DO FORMULÁRIO ---
def _save_fiscal_data(nome_empresa, periodo, form_data):
    """Salva todos os dados do formulário fiscal para uma empresa e período."""
    dados_gerais = carregar_dados()
    if nome_empresa not in dados_gerais:
        return False

    dados_empresa_especifica = dados_gerais[nome_empresa]
    periodos_empresa = dados_empresa_especifica.get('periodos', {})
    if periodo not in periodos_empresa:
        periodos_empresa[periodo] = {}
    dados_periodo = periodos_empresa[periodo]

    # Salva os campos de texto
    dados_periodo['faturamento'] = {campo: para_float(form_data.get(campo)) for campo in CAMPOS_FATURAMENTO}
    dados_periodo['despesas'] = {campo: para_float(form_data.get(campo)) for campo in CAMPOS_DESPESAS}
    dados_periodo['impostos_federal'] = {campo: para_float(form_data.get(campo)) for campo in CAMPOS_IMPOSTOS_FEDERAL}
    dados_periodo['impostos_estadual'] = {campo: para_float(form_data.get(campo)) for campo in CAMPOS_IMPOSTOS_ESTADUAL}
    dados_periodo['impostos_municipal'] = {campo: para_float(form_data.get(campo)) for campo in CAMPOS_IMPOSTOS_MUNICIPAL}
    dados_periodo['retencoes_federal'] = {campo: para_float(form_data.get(campo)) for campo in CAMPOS_RETENCOES_FEDERAL}
    
    # Salva o estado dos checkboxes
    dados_periodo['faturamento']['lancado'] = 'fat_lancado' in form_data
    dados_periodo['faturamento']['concluido'] = 'fat_concluido' in form_data
    dados_periodo['impostos_federal']['lancado'] = 'imp_fed_lancado' in form_data
    dados_periodo['impostos_federal']['concluido'] = 'imp_fed_concluido' in form_data
    dados_periodo['impostos_estadual']['lancado'] = 'imp_est_lancado' in form_data
    dados_periodo['impostos_estadual']['concluido'] = 'imp_est_concluido' in form_data
    dados_periodo['impostos_municipal']['lancado'] = 'imp_mun_lancado' in form_data
    dados_periodo['impostos_municipal']['concluido'] = 'imp_mun_concluido' in form_data
    dados_periodo['retencoes_federal']['lancado'] = 'ret_fed_lancado' in form_data
    dados_periodo['retencoes_federal']['concluido'] = 'ret_fed_concluido' in form_data
    dados_periodo['retencoes_federal']['sem_notas'] = 'ret_fed_sem_notas' in form_data
    dados_periodo['retencoes_federal']['dispensado'] = 'ret_fed_dispensado' in form_data

    dados_gerais[nome_empresa]['periodos'] = periodos_empresa
    salvar_dados(dados_gerais)
    return True

@fiscal_bp.route('/selecionar_departamento/<path:nome_empresa>/<periodo>')
@login_required
def selecionar_departamento(nome_empresa, periodo):
    dados = carregar_dados()
    return render_template('selecionar_departamento.html', nome_empresa=nome_empresa, periodo=periodo, dados=dados)

@fiscal_bp.route('/dados/<path:nome_empresa>/<periodo>', methods=['GET', 'POST'])
@login_required
def dados_empresa(nome_empresa, periodo):
    if request.method == 'POST':
        if _save_fiscal_data(nome_empresa, periodo, request.form):
            flash(f'Dados para {nome_empresa} ({periodo}) salvos com sucesso!', 'success')
        else:
            flash('Erro ao salvar os dados.', 'danger')
        return redirect(url_for('fiscal.dados_empresa', nome_empresa=nome_empresa, periodo=periodo))
    
    dados_gerais = carregar_dados()
    if nome_empresa not in dados_gerais:
        flash('Empresa não encontrada.', 'danger')
        return redirect(url_for('main.index'))
    
    dados_empresa_especifica = dados_gerais[nome_empresa]
    dados_atuais_periodo = dados_empresa_especifica.get('periodos', {}).get(periodo, {})
    status_periodo = dados_atuais_periodo.get('status', 'Em Aberto')
    
    return render_template('dados_empresa.html', 
                           nome_empresa=nome_empresa, periodo=periodo,
                           dados_empresa=dados_empresa_especifica, dados=dados_atuais_periodo, status=status_periodo,
                           campos_faturamento=CAMPOS_FATURAMENTO, campos_despesas=CAMPOS_DESPESAS,
                           campos_impostos_federal=CAMPOS_IMPOSTOS_FEDERAL, campos_impostos_estadual=CAMPOS_IMPOSTOS_ESTADUAL,
                           campos_impostos_municipal=CAMPOS_IMPOSTOS_MUNICIPAL, campos_retencoes_federal=CAMPOS_RETENCOES_FEDERAL)

@fiscal_bp.route('/finalize_month/<path:nome_empresa>/<periodo>', methods=['POST'])
@login_required
def finalize_month(nome_empresa, periodo):
    _save_fiscal_data(nome_empresa, periodo, request.form)
    
    dados_gerais = carregar_dados()
    if nome_empresa in dados_gerais:
        if 'periodos' not in dados_gerais[nome_empresa]: dados_gerais[nome_empresa]['periodos'] = {}
        if periodo not in dados_gerais[nome_empresa]['periodos']: dados_gerais[nome_empresa]['periodos'][periodo] = {}
        dados_gerais[nome_empresa]['periodos'][periodo]['status'] = 'Finalizado'
        salvar_dados(dados_gerais)
        flash('Mês finalizado com sucesso!', 'success')
    else:
        flash('Erro ao finalizar o mês. Empresa não encontrada.', 'danger')
    return redirect(url_for('fiscal.dados_empresa', nome_empresa=nome_empresa, periodo=periodo))

@fiscal_bp.route('/reopen_month/<path:nome_empresa>/<periodo>', methods=['POST'])
@login_required
def reopen_month(nome_empresa, periodo):
    # A chamada para _save_fiscal_data foi REMOVIDA daqui.
    # Esta função agora apenas altera o status.

    dados_gerais = carregar_dados()
    if nome_empresa in dados_gerais and periodo in dados_gerais[nome_empresa].get('periodos', {}):
        dados_gerais[nome_empresa]['periodos'][periodo]['status'] = 'Em Aberto'
        salvar_dados(dados_gerais)
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

    for nome_empresa, detalhes_empresa in sorted(dados.items()):
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
        return redirect(url_for('main.index'))
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return Response(buffer, mimetype='application/vnd.openxmlformats-officedocument.sheet', headers={"Content-Disposition": f"attachment;filename={filename}"})