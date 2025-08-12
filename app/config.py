# app/config.py

# Chave secreta para a segurança da sessão
SECRET_KEY = 'uma-chave-secreta-muito-dificil-de-adivinhar'

# Constantes da aplicação
NOME_ARQUIVO_DADOS = 'dados_empresas.json'
USUARIO_PADRAO = 'admin'
SENHA_PADRAO = 'contajur2025'

# Listas de Campos para os formulários
CAMPOS_FATURAMENTO = [
    "Serviços tributados", "Serviços retidos", "Venda (indústria/imóveis)",
    "Revenda mercadorias tributárias", "Revenda mercadorias não tributárias",
    "Revenda de mercadoria monofásica", "Locação", "Receita sem nota fiscal"
]
CAMPOS_DESPESAS = [
    "Compras para revenda", "Compras para uso/consumo",
    "Compras para ativo imobilizado", "Serviços tomados com nota fiscal"
]
CAMPOS_IMPOSTOS_FEDERAL = ["Simples", "PIS", "COFINS", "IRPJ", "CSLL", "IOF", "IPI"]
CAMPOS_IMPOSTOS_ESTADUAL = ["ICMS próprio", "ICMS ST próprio", "DIFAL", "Antecipação", "ICMS ST Entradas", "FEM"]
CAMPOS_IMPOSTOS_MUNICIPAL = ["ISSQN a pagar", "ISSQN Retido (NF própria)"]
CAMPOS_RETENCOES_FEDERAL = ["CSRF (Retido)", "IRRF (Retido)", "INSS (Retido)", "ISSQN (Retido)"]
