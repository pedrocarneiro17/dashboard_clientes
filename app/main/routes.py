# app/main/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db, User, Empresa, Periodo # Importa o db e os Modelos
from app.utils import login_required 
from datetime import datetime

main_bp = Blueprint('main', __name__)

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Procura o utilizador no banco de dados
        user = User.query.filter_by(username=username).first()

        # Verifica se o utilizador existe e se a senha está correta
        if user and user.check_password(password):
            session['logged_in'] = True
            session['username'] = user.username
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('main.index'))
        else:
            flash('Utilizador ou senha inválidos.', 'danger')
            
    return render_template('login.html')

@main_bp.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('main.login'))

@main_bp.route('/')
@login_required
def index():
    # Busca todas as empresas ativas do banco de dados, em ordem alfabética
    empresas_ativas = Empresa.query.filter_by(active=True).order_by(Empresa.nome).all()
    
    now = datetime.now()
    search_ano = request.args.get('search_ano', str(now.year))
    search_mes = request.args.get('search_mes', f"{now.month:02d}")
    search_status = request.args.get('search_status')
    
    periodo_pesquisado = f"{search_ano}-{search_mes}"
    
    # Lógica para os gráficos de status
    empresas_fiscal_em_aberto = []
    empresas_fiscal_finalizadas = []
    empresas_dp_em_aberto = []
    empresas_dp_finalizadas = []
    
    # Consulta os períodos do mês pesquisado para todas as empresas ativas
    ids_empresas_ativas = [e.id for e in empresas_ativas]
    periodos_do_mes = Periodo.query.filter(
        Periodo.empresa_id.in_(ids_empresas_ativas),
        Periodo.ano_mes == periodo_pesquisado
    ).all()

    # Mapeia id da empresa para o nome para facilitar
    mapa_id_nome = {e.id: e.nome for e in empresas_ativas}
    
    # Processa os status
    empresas_com_periodo = {p.empresa_id for p in periodos_do_mes}
    
    for p in periodos_do_mes:
        nome_empresa = mapa_id_nome.get(p.empresa_id)
        if nome_empresa:
            # Status Fiscal
            if p.status == 'Finalizado':
                empresas_fiscal_finalizadas.append(nome_empresa)
            else:
                empresas_fiscal_em_aberto.append(nome_empresa)
            # Status DP
            if p.dp_status == 'Finalizado':
                empresas_dp_finalizadas.append(nome_empresa)
            else:
                empresas_dp_em_aberto.append(nome_empresa)

    # Empresas ativas que não têm um registro de período para o mês são consideradas "Em Aberto"
    for empresa in empresas_ativas:
        if empresa.id not in empresas_com_periodo:
            empresas_fiscal_em_aberto.append(empresa.nome)
            empresas_dp_em_aberto.append(empresa.nome)

    # A lógica de filtro avançado precisará ser refatorada para usar o banco de dados.
    # Por enquanto, vamos manter a estrutura principal funcionando.
    empresas_resultado_filtro = None
    status_pesquisado_label = None
    if search_status:
        # Aqui entraria a nova lógica de consulta ao banco de dados para os filtros
        pass

    meses = [f"{i:02d}" for i in range(1, 13)]
    anos = [str(i) for i in range(2023, now.year + 2)]
    
    return render_template('index.html', 
                           empresas=empresas_ativas, 
                           meses=meses, 
                           anos=anos, 
                           ano_atual=str(now.year), 
                           mes_atual=f"{now.month:02d}",
                           empresas_resultado_filtro=empresas_resultado_filtro,
                           empresas_fiscal_em_aberto=empresas_fiscal_em_aberto,
                           empresas_fiscal_finalizadas=empresas_fiscal_finalizadas,
                           empresas_dp_em_aberto=empresas_dp_em_aberto,
                           empresas_dp_finalizadas=empresas_dp_finalizadas,
                           periodo_pesquisado=periodo_pesquisado,
                           search_ano=search_ano, 
                           search_mes=search_mes,
                           search_status=search_status,
                           filtro_label=status_pesquisado_label)