# app/dashboard/routes.py
from flask import Blueprint, render_template
from app.utils import carregar_dados, para_float, login_required

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

    # --- NOVO: Consolidação dos dados de Faturamento ---
    faturamento_original = dados_periodo.get('faturamento', {})
    
    valor_servicos = para_float(faturamento_original.get('Serviços tributados')) + \
                     para_float(faturamento_original.get('Serviços retidos'))

    valor_revenda = para_float(faturamento_original.get('Revenda mercadorias tributadas')) + \
                    para_float(faturamento_original.get('Revenda mercadorias não tributárias')) + \
                    para_float(faturamento_original.get('Revenda de mercadoria monofásica'))

    faturamento_consolidado = {
        "SERVIÇOS": valor_servicos,
        "REVENDA DE MERCADORIAS": valor_revenda,
        "VENDA (INDÚSTRIA/IMÓVEIS)": para_float(faturamento_original.get('Venda (indústria/imóveis)')),
        "LOCAÇÃO": para_float(faturamento_original.get('Locação')),
        "RECEITA SEM NOTA FISCAL": para_float(faturamento_original.get('Receita sem nota fiscal'))
    }

    # --- Preparação dos Gráficos ---
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

    # --- Cálculo dos Resumos com Lucro Líquido ---
    liquido_colaboradores = para_float(dp_data.get('LIQUIDO_COLABORADORES'))
    liquido_empregadores = para_float(dp_data.get('LIQUIDO_EMPREGADORES'))
    valor_gps = para_float(dp_data.get('VALOR_GPS'))
    valor_fgts_mensal = para_float(dp_data.get('VALOR_FGTS_MENSAL'))
    valor_fgts_rescisoria = para_float(dp_data.get('VALOR_FGTS_RESCISORIA'))

    total_faturamento = sum(para_float(v) for k, v in faturamento_original.items() if k not in campos_nao_grafico)
    total_despesas_fiscal = sum(fiscal_charts[1]['data']['data'])
    total_impostos_fiscal = sum(fiscal_charts[2]['data']['data']) + sum(fiscal_charts[3]['data']['data']) + sum(fiscal_charts[4]['data']['data'])

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

    return render_template(
        'dashboard_page.html',
        nome_empresa=nome_empresa,
        periodo=periodo,
        dados_empresa=dados_empresa,
        fiscal_charts=fiscal_charts_filtrados,
        dp_chart=dp_chart,
        resumo_fiscal=resumo_fiscal,
        situacao_colaboradores=situacao_colaboradores,
        colaboradores=colaboradores
    )