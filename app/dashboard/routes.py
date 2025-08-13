# app/dashboard/routes.py
from flask import Blueprint, render_template, request, jsonify
from app.utils import carregar_dados, para_float, login_required
from datetime import datetime
from dateutil.rrule import rrule, MONTHLY

dashboard_bp = Blueprint('dashboard', __name__, template_folder='templates')

@dashboard_bp.route('/dashboard/<path:nome_empresa>/<periodo>')
@login_required
def view_dashboard(nome_empresa, periodo):
    """Exibe o dashboard unificado com dados Fiscais e de DP."""
    dados_gerais = carregar_dados()
    dados_empresa = dados_gerais.get(nome_empresa, {})
    dados_periodo = dados_empresa.get('periodos', {}).get(periodo, {})

    campos_nao_grafico = {'lancado', 'concluido', 'sem_notas', 'dispensado'}

    def preparar_dados_grafico(dados_dict, chaves_filtro=None):
        dados_dict = dados_dict or {}
        if chaves_filtro:
            dados_filtrados = {k: dados_dict.get(k, 0) for k in chaves_filtro}
        else:
            dados_filtrados = dados_dict
        
        labels = [k.replace('_', ' ').upper() for k, v in dados_filtrados.items() if k not in campos_nao_grafico and para_float(v) > 0]
        data = [para_float(v) for k, v in dados_filtrados.items() if k not in campos_nao_grafico and para_float(v) > 0]
        return {'labels': labels, 'data': data}

    faturamento_original = dados_periodo.get('faturamento', {})
    valor_servicos = para_float(faturamento_original.get('Serviços tributados')) + para_float(faturamento_original.get('Serviços retidos'))
    valor_revenda = para_float(faturamento_original.get('Revenda mercadorias tributadas')) + para_float(faturamento_original.get('Revenda mercadorias não tributárias')) + para_float(faturamento_original.get('Revenda de mercadoria monofásica'))
    faturamento_consolidado = {
        "SERVIÇOS": valor_servicos,
        "REVENDA DE MERCADORIAS": valor_revenda,
        "VENDA (INDÚSTRIA/IMÓVEIS)": para_float(faturamento_original.get('Venda (indústria/imóveis)')),
        "LOCAÇÃO": para_float(faturamento_original.get('Locação')),
        "RECEITA SEM NOTA FISCAL": para_float(faturamento_original.get('Receita sem nota fiscal'))
    }

    fiscal_charts = [
        {"title": "Faturamento", "data": preparar_dados_grafico(faturamento_consolidado), "id": "chartFaturamento"},
        {"title": "Despesas", "data": preparar_dados_grafico(dados_periodo.get('despesas')), "id": "chartDespesas"},
        {"title": "Impostos Federais", "data": preparar_dados_grafico(dados_periodo.get('impostos_federal')), "id": "chartImpFederal"},
        {"title": "Impostos Estaduais", "data": preparar_dados_grafico(dados_periodo.get('impostos_estadual')), "id": "chartImpEstadual"},
        {"title": "Impostos Municipais", "data": preparar_dados_grafico(dados_periodo.get('impostos_municipal')), "id": "chartImpMunicipal"},
        {"title": "Retenções Federais", "data": preparar_dados_grafico(dados_periodo.get('retencoes_federal')), "id": "chartRetFederal"}
    ]
    fiscal_charts_filtrados = [chart for chart in fiscal_charts if chart['data']['data']]
    
    dp_data = dados_periodo.get('departamento_pessoal', {})
    if dp_data:
        if 'VALOR_GFD_MENSAL' in dp_data: dp_data['VALOR_FGTS_MENSAL'] = dp_data.pop('VALOR_GFD_MENSAL')
        if 'VALOR_GFD_RESCISORIA' in dp_data: dp_data['VALOR_FGTS_RESCISORIA'] = dp_data.pop('VALOR_GFD_RESCISORIA')
            
    dp_keys = ['LIQUIDO_COLABORADORES', 'LIQUIDO_EMPREGADORES', 'VALOR_GPS', 'VALOR_FGTS_MENSAL', 'VALOR_FGTS_RESCISORIA']
    dp_chart_data = preparar_dados_grafico(dp_data, dp_keys)
    dp_chart = {"title": "Valores Departamento Pessoal", "data": dp_chart_data, "id": "chartDP"} if dp_chart_data['data'] else None

    liquido_colaboradores = para_float(dp_data.get('LIQUIDO_COLABORADORES'))
    liquido_empregadores = para_float(dp_data.get('LIQUIDO_EMPREGADORES'))
    valor_gps = para_float(dp_data.get('VALOR_GPS'))
    valor_fgts_mensal = para_float(dp_data.get('VALOR_FGTS_MENSAL'))
    valor_fgts_rescisoria = para_float(dp_data.get('VALOR_FGTS_RESCISORIA'))
    total_faturamento = sum(para_float(v) for k, v in faturamento_original.items() if k not in campos_nao_grafico)
    total_despesas_fiscal = sum(para_float(v) for k, v in dados_periodo.get('despesas', {}).items() if k not in campos_nao_grafico)
    total_impostos_fiscal = sum(para_float(v) for k, v in dados_periodo.get('impostos_federal', {}).items() if k not in campos_nao_grafico) + \
                            sum(para_float(v) for k, v in dados_periodo.get('impostos_estadual', {}).items() if k not in campos_nao_grafico) + \
                            sum(para_float(v) for k, v in dados_periodo.get('impostos_municipal', {}).items() if k not in campos_nao_grafico)

    total_impostos_geral = total_impostos_fiscal + valor_gps + valor_fgts_mensal + valor_fgts_rescisoria
    total_despesas_e_custos = total_despesas_fiscal + liquido_colaboradores + liquido_empregadores
    lucro_liquido = total_faturamento - total_despesas_e_custos - total_impostos_geral

    resumo_fiscal = {
        "total_faturamento": total_faturamento,
        "total_despesas_e_custos": total_despesas_e_custos,
        "total_impostos": total_impostos_geral,
        "lucro_liquido": lucro_liquido
    }
    
    situacao_colaboradores = dp_data.get('SITUACAO_COLABORADORES')
    colaboradores = dp_data.get('COLABORADORES', [])
    
    anos = [str(i) for i in range(2023, datetime.now().year + 2)]
    meses = [f"{i:02d}" for i in range(1, 13)]

    return render_template(
        'dashboard_page.html',
        nome_empresa=nome_empresa, periodo=periodo, dados_empresa=dados_empresa,
        fiscal_charts=fiscal_charts_filtrados, dp_chart=dp_chart, resumo_fiscal=resumo_fiscal,
        situacao_colaboradores=situacao_colaboradores, colaboradores=colaboradores,
        anos=anos, meses=meses
    )

@dashboard_bp.route('/api/comparativo_data')
@login_required
def comparativo_data():
    """API que retorna os dados consolidados para os gráficos comparativos."""
    nome_empresa = request.args.get('nome_empresa')
    periodo_inicio = request.args.get('periodo_inicio')
    periodo_fim = request.args.get('periodo_fim')

    if not all([nome_empresa, periodo_inicio, periodo_fim]):
        return jsonify({"erro": "Parâmetros inválidos"}), 400

    dados_gerais = carregar_dados()
    periodos_empresa = dados_gerais.get(nome_empresa, {}).get('periodos', {})
    
    try:
        start_date = datetime.strptime(periodo_inicio, "%Y-%m")
        end_date = datetime.strptime(periodo_fim, "%Y-%m")
    except ValueError:
        return jsonify({"erro": "Formato de data inválido. Use AAAA-MM."}), 400
    
    labels = []
    receitas_data, despesas_custos_data, lucro_liquido_data = [], [], []
    impostos_fed_data, impostos_est_data, impostos_mun_data, retencoes_fed_data = [], [], [], []

    for dt in rrule(MONTHLY, dtstart=start_date, until=end_date):
        periodo = dt.strftime("%Y-%m")
        dados_periodo = periodos_empresa.get(periodo, {})

        if dados_periodo and dados_periodo.get('status') == 'Finalizado' and dados_periodo.get('dp_status') == 'Finalizado':
            labels.append(dt.strftime("%m/%Y"))
            
            faturamento_mes = dados_periodo.get('faturamento', {})
            despesas_mes = dados_periodo.get('despesas', {})
            dp_mes = dados_periodo.get('departamento_pessoal', {})

            total_faturamento = sum(para_float(v) for k, v in faturamento_mes.items() if k not in ['lancado', 'concluido'])
            total_despesas_fiscal = sum(para_float(v) for k, v in despesas_mes.items() if k not in ['lancado', 'concluido'])
            liquido_colaboradores = para_float(dp_mes.get('LIQUIDO_COLABORADORES'))
            liquido_empregadores = para_float(dp_mes.get('LIQUIDO_EMPREGADORES'))
            total_despesas_e_custos = total_despesas_fiscal + liquido_colaboradores + liquido_empregadores

            impostos_fed = sum(para_float(v) for k, v in dados_periodo.get('impostos_federal', {}).items() if k not in ['lancado', 'concluido'])
            impostos_est = sum(para_float(v) for k, v in dados_periodo.get('impostos_estadual', {}).items() if k not in ['lancado', 'concluido'])
            impostos_mun = sum(para_float(v) for k, v in dados_periodo.get('impostos_municipal', {}).items() if k not in ['lancado', 'concluido'])
            retencoes = sum(para_float(v) for k, v in dados_periodo.get('retencoes_federal', {}).items() if k not in ['lancado', 'concluido', 'sem_notas', 'dispensado'])
            
            gps = para_float(dp_mes.get('VALOR_GPS'))
            fgts_mensal = para_float(dp_mes.get('VALOR_GFD_MENSAL') or dp_mes.get('VALOR_FGTS_MENSAL'))
            fgts_rescisoria = para_float(dp_mes.get('VALOR_GFD_RESCISORIA') or dp_mes.get('VALOR_FGTS_RESCISORIA'))
            
            total_impostos_geral = impostos_fed + impostos_est + impostos_mun + gps + fgts_mensal + fgts_rescisoria
            lucro_liquido = total_faturamento - total_despesas_e_custos - total_impostos_geral

            receitas_data.append(total_faturamento)
            despesas_custos_data.append(total_despesas_e_custos)
            lucro_liquido_data.append(lucro_liquido)
            impostos_fed_data.append(impostos_fed)
            impostos_est_data.append(impostos_est)
            impostos_mun_data.append(impostos_mun)
            retencoes_fed_data.append(retencoes)

    return jsonify({
        "labels": labels,
        "grafico1": {"receitas": receitas_data, "despesas": despesas_custos_data, "lucro": lucro_liquido_data},
        "grafico2": {"federais": impostos_fed_data, "estaduais": impostos_est_data, "municipais": impostos_mun_data, "retencoes": retencoes_fed_data}
    })