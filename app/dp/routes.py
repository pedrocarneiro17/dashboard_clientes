# app/dp/routes.py
from flask import Blueprint, render_template, request, flash, redirect, url_for
from app.utils import carregar_dados, salvar_dados, login_required
from app.pdf_parser import extrair_dados_pdf

dp_bp = Blueprint('dp', __name__)

@dp_bp.route('/upload_dp_page')
@login_required
def upload_dp_page():
    """Mostra a página de upload de PDFs do DP."""
    return render_template('upload_dp.html')

@dp_bp.route('/upload_dp', methods=['POST'])
@login_required
def upload_dp():
    """Processa o upload dos PDFs, salva os dados e finaliza o status do DP."""
    files = request.files.getlist('pdf_files')
    if not files or files[0].filename == '':
        flash('Nenhum arquivo selecionado.', 'warning')
        return redirect(url_for('dp.upload_dp_page'))

    dados_gerais = carregar_dados()
    cnpj_map = {detalhes['cnpj']: nome for nome, detalhes in dados_gerais.items() if 'cnpj' in detalhes}
    
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

                periodo = dados_extraidos.get("PERIODO")
                cnpj = dados_extraidos.get("CNPJ")

                if not periodo:
                    falha_periodo.append(file.filename)
                    continue
                
                if cnpj in cnpj_map:
                    nome_empresa = cnpj_map[cnpj]
                    if 'periodos' not in dados_gerais[nome_empresa]:
                        dados_gerais[nome_empresa]['periodos'] = {}
                    if periodo not in dados_gerais[nome_empresa]['periodos']:
                        dados_gerais[nome_empresa]['periodos'][periodo] = {}
                    
                    dados_gerais[nome_empresa]['periodos'][periodo]['departamento_pessoal'] = dados_extraidos
                    # Ao carregar o PDF, o status do DP é automaticamente definido como Finalizado.
                    dados_gerais[nome_empresa]['periodos'][periodo]['dp_status'] = 'Finalizado'
                    
                    sucesso_count += 1
                else:
                    falha_cnpj.append(file.filename)

            except Exception as e:
                falha_leitura.append(f"{file.filename} (erro: {e})")

    if sucesso_count > 0:
        salvar_dados(dados_gerais)
        flash(f'{sucesso_count} arquivo(s) processado(s) com sucesso!', 'success')
    
    if falha_leitura:
        flash(f'Falha ao ler os seguintes arquivos (verifique se não estão corrompidos): {", ".join(falha_leitura)}', 'danger')
    if falha_cnpj:
        flash(f'CNPJ não encontrado no sistema para os arquivos: {", ".join(falha_cnpj)}', 'warning')
    if falha_periodo:
        flash(f'Não foi possível determinar o período para os arquivos: {", ".join(falha_periodo)}', 'warning')

    return redirect(url_for('dp.upload_dp_page'))

@dp_bp.route('/dados_dp/<path:nome_empresa>/<periodo>')
@login_required
def dados_dp(nome_empresa, periodo):
    """Exibe os dados de DP de uma empresa para um período."""
    dados_gerais = carregar_dados()
    dados_empresa = dados_gerais.get(nome_empresa, {})
    dados_periodo = dados_empresa.get('periodos', {}).get(periodo, {})
    
    dados_dp_especifico = dados_periodo.get('departamento_pessoal')
    status_dp = dados_periodo.get('dp_status', 'Em Aberto')
    
    return render_template('dados_dp.html', 
                           nome_empresa=nome_empresa, 
                           periodo=periodo,
                           dados_dp=dados_dp_especifico,
                           status_dp=status_dp)

@dp_bp.route('/delete_dp_data/<path:nome_empresa>/<periodo>', methods=['POST'])
@login_required
def delete_dp_data(nome_empresa, periodo):
    """Exclui os dados de DP de um mês e reabre o status."""
    dados_gerais = carregar_dados()
    
    periodos = dados_gerais.get(nome_empresa, {}).get('periodos', {})
    if periodo in periodos:
        # Remove a chave 'departamento_pessoal'
        if 'departamento_pessoal' in periodos[periodo]:
            del periodos[periodo]['departamento_pessoal']
            periodos[periodo]['dp_status'] = 'Em Aberto'
            salvar_dados(dados_gerais)
            flash('Dados de DP excluídos com sucesso!', 'success')
        else:
            flash('Nenhum dado de DP encontrado para este período.', 'warning')
    else:
        flash('Período não encontrado.', 'warning')

    return redirect(url_for('dp.dados_dp', nome_empresa=nome_empresa, periodo=periodo))