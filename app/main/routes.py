# app/main/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.utils import carregar_dados, login_required
from app.config import USUARIO_PADRAO, SENHA_PADRAO
from datetime import datetime

main_bp = Blueprint('main', __name__)

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == USUARIO_PADRAO and request.form['password'] == SENHA_PADRAO:
            session['logged_in'] = True
            session['username'] = request.form['username']
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('main.index'))
        else:
            flash('Usuário ou senha inválidos.', 'danger')
    return render_template('login.html')

@main_bp.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('main.login'))

@main_bp.route('/')
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
        status_labels = {
            "fiscal_em_aberto": "Fiscal - Em Aberto", "fiscal_finalizado": "Fiscal - Finalizado",
            "dp_em_aberto": "Dep. Pessoal - Em Aberto", "dp_finalizado": "Dep. Pessoal - Finalizado",
            "fat_lancado": "Faturamento Lançado", "fat_nao_lancado": "Faturamento Não Lançado",
            "fat_concluido": "Faturamento Concluído", "fat_nao_concluido": "Faturamento Não Concluído",
            "imp_fed_lancado": "Impostos Federais Lançado", "imp_fed_nao_lancado": "Impostos Federais Não Lançado",
            "imp_fed_concluido": "Impostos Federais Concluído", "imp_fed_nao_concluido": "Impostos Federais Não Concluído",
            "imp_est_lancado": "Impostos Estaduais Lançado", "imp_est_nao_lancado": "Impostos Estaduais Não Lançado",
            "imp_est_concluido": "Impostos Estaduais Concluído", "imp_est_nao_concluido": "Impostos Estaduais Não Concluído",
            "imp_mun_lancado": "Impostos Municipais Lançado", "imp_mun_nao_lancado": "Impostos Municipais Não Lançado",
            "imp_mun_concluido": "Impostos Municipais Concluído", "imp_mun_nao_concluido": "Impostos Municipais Não Concluído",
            "ret_fed_lancado": "Retenções Federais Lançado", "ret_fed_nao_lancado": "Retenções Federais Não Lançado",
            "ret_fed_concluido": "Retenções Federais Concluído", "ret_fed_nao_concluido": "Retenções Federais Não Concluído",
            "ret_fed_sem_notas": "Retenções Federais Sem Notas", "ret_fed_nao_sem_notas": "Retenções Federais Com Notas",
            "ret_fed_dispensado": "Retenções Federais Dispensado", "ret_fed_nao_dispensado": "Retenções Federais Não Dispensado"
        }
        status_pesquisado_label = status_labels.get(search_status, "")

        if search_status == 'fiscal_em_aberto': empresas_resultado_filtro = empresas_fiscal_em_aberto
        elif search_status == 'fiscal_finalizado': empresas_resultado_filtro = empresas_fiscal_finalizadas
        elif search_status == 'dp_em_aberto': empresas_resultado_filtro = empresas_dp_em_aberto
        elif search_status == 'dp_finalizado': empresas_resultado_filtro = empresas_dp_finalizadas
        else:
            for nome, detalhes in empresas_ordenadas.items():
                dados_periodo = detalhes.get('periodos', {}).get(periodo_pesquisado, {})
                match = False
                key_map = { 'fat': 'faturamento', 'imp_fed': 'impostos_federal', 'imp_est': 'impostos_estadual', 'imp_mun': 'impostos_municipal', 'ret_fed': 'retencoes_federal' }
                parts = search_status.split('_')
                if len(parts) >= 2:
                    check_type = parts[-1]
                    prefix_parts = parts[:-1]
                    is_negative = "nao" in prefix_parts
                    if is_negative: prefix_parts.remove("nao")
                    prefix = "_".join(prefix_parts)
                    category_key = key_map.get(prefix)
                    if category_key:
                        is_checked = dados_periodo.get(category_key, {}).get(check_type, False)
                        if is_negative:
                            if not is_checked: match = True
                        else:
                            if is_checked: match = True
                if match:
                    empresas_resultado_filtro.append(nome)

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
