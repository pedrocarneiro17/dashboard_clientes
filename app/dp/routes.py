# app/dp/routes.py
from flask import Blueprint, render_template, request, flash, redirect, url_for
from app import db, Empresa, Periodo # Importa o db e os Modelos
from app.utils import login_required
from app.pdf_parser import extrair_dados_pdf
from datetime import datetime
from dateutil.relativedelta import relativedelta

dp_bp = Blueprint('dp', __name__)

@dp_bp.route('/upload_dp_page')
@login_required
def upload_dp_page():
    """Mostra a página de upload de PDFs do DP."""
    return render_template('upload_dp.html')

@dp_bp.route('/upload_dp', methods=['POST'])
@login_required
def upload_dp():
    """Processa o upload dos PDFs, salva os dados no banco e finaliza o status do DP."""
    files = request.files.getlist('pdf_files')
    if not files or files[0].filename == '':
        flash('Nenhum arquivo selecionado.', 'warning')
        return redirect(url_for('dp.upload_dp_page'))

    sucesso_count = 0
    falha_leitura = []
    falha_cnpj = []
    falha_periodo = []

    for file in files:
        if file and file.filename.endswith('.pdf'):
            try:
                dados_extraidos = extrair_dados_pdf(file.stream)
                
                if "erro" in dados_extraidos:
                    falha_leitura.append(file.filename)
                    continue

                periodo_str = dados_extraidos.get("PERIODO")
                cnpj = dados_extraidos.get("CNPJ")

                if not periodo_str:
                    falha_periodo.append(file.filename)
                    continue
                
                # Procura a empresa no banco de dados pelo CNPJ
                empresa = Empresa.query.filter_by(cnpj=cnpj).first()
                
                if empresa:
                    # Procura pelo período; se não existir, cria um novo
                    periodo_obj = Periodo.query.filter_by(empresa_id=empresa.id, ano_mes=periodo_str).first()
                    if not periodo_obj:
                        periodo_obj = Periodo(empresa_id=empresa.id, ano_mes=periodo_str)
                        db.session.add(periodo_obj)
                    
                    # Salva os dados extraídos no campo JSON e atualiza o status
                    periodo_obj.dados_dp = dados_extraidos
                    periodo_obj.dp_status = 'Finalizado'
                    
                    sucesso_count += 1
                else:
                    falha_cnpj.append(file.filename)

            except Exception as e:
                falha_leitura.append(f"{file.filename} (erro: {e})")

    if sucesso_count > 0:
        db.session.commit() # Salva todas as alterações no banco de uma só vez
        flash(f'{sucesso_count} arquivo(s) processado(s) com sucesso!', 'success')
    
    if falha_leitura:
        flash(f'Falha ao ler os seguintes arquivos: {", ".join(falha_leitura)}', 'danger')
    if falha_cnpj:
        flash(f'CNPJ não encontrado no sistema para os arquivos: {", ".join(falha_cnpj)}', 'warning')
    if falha_periodo:
        flash(f'Não foi possível determinar o período para os arquivos: {", ".join(falha_periodo)}', 'warning')

    return redirect(url_for('dp.upload_dp_page'))

@dp_bp.route('/dados_dp/<path:nome_empresa>/<periodo>')
@login_required
def dados_dp(nome_empresa, periodo):
    """Exibe os dados de DP de uma empresa para um período, lendo do banco de dados."""
    empresa = Empresa.query.filter_by(nome=nome_empresa).first_or_404()
    periodo_obj = Periodo.query.filter_by(empresa_id=empresa.id, ano_mes=periodo).first()

    dados_dp_especifico = periodo_obj.dados_dp if periodo_obj and periodo_obj.dados_dp else None
    status_dp = periodo_obj.dp_status if periodo_obj else 'Em Aberto'
    
    aniversariantes = []
    if dados_dp_especifico and 'COLABORADORES' in dados_dp_especifico:
        try:
            data_relatorio = datetime.strptime(periodo, "%Y-%m")
            proximo_mes_data = data_relatorio + relativedelta(months=1)
            proximo_mes_numero = proximo_mes_data.month

            for col in dados_dp_especifico['COLABORADORES']:
                if col.get('admissao'):
                    data_admissao = datetime.strptime(col['admissao'], "%d/%m/%Y")
                    if data_admissao.month == proximo_mes_numero:
                        anos_de_casa = proximo_mes_data.year - data_admissao.year
                        if anos_de_casa > 0:
                            aniversariantes.append({"nome": col['nome'], "anos": anos_de_casa})
        except (ValueError, TypeError) as e:
            print(f"Erro ao processar datas para aniversariantes: {e}")

    return render_template('dados_dp.html', 
                           nome_empresa=nome_empresa, 
                           periodo=periodo,
                           dados_dp=dados_dp_especifico,
                           status_dp=status_dp,
                           aniversariantes=aniversariantes)

@dp_bp.route('/delete_dp_data/<path:nome_empresa>/<periodo>', methods=['POST'])
@login_required
def delete_dp_data(nome_empresa, periodo):
    """Exclui os dados de DP de um mês no banco de dados e reabre o status."""
    empresa = Empresa.query.filter_by(nome=nome_empresa).first_or_404()
    periodo_obj = Periodo.query.filter_by(empresa_id=empresa.id, ano_mes=periodo).first()

    if periodo_obj:
        periodo_obj.dados_dp = None # Apaga os dados do campo JSON
        periodo_obj.dp_status = 'Em Aberto' # Reseta o status
        db.session.commit()
        flash('Dados do Departamento Pessoal para este mês foram excluídos com sucesso.', 'success')
    else:
        flash('Período não encontrado para exclusão.', 'warning')
        
    return redirect(url_for('dp.dados_dp', nome_empresa=nome_empresa, periodo=periodo))