# app/config.py
import os

# Chave secreta para a segurança da sessão (lida de variável de ambiente)
SECRET_KEY = os.getenv('SECRET_KEY', 'uma-chave-secreta-padrão-para-desenvolvimento')

# As constantes de login e nome do arquivo JSON foram REMOVIDAS.

# Listas de Campos para os formulários (isto pode continuar aqui)
CAMPOS_FATURAMENTO = [
    "Serviços tributados", "Serviços retidos", "Venda (indústria/imóveis)",
    "Revenda mercadorias tributadas", "Revenda mercadorias não tributárias",
    "Revenda de mercadoria monofásica", "Locação", "Outras receitas"
]
CAMPOS_DESPESAS = [
    "Compras para revenda", "Compras para uso/consumo",
    "Compras para ativo imobilizado", "Serviços tomados com nota fiscal"
]
CAMPOS_IMPOSTOS_FEDERAL = ["Simples", "PIS", "COFINS", "IRPJ", "CSLL", "IOF", "IPI"]
CAMPOS_IMPOSTOS_ESTADUAL = ["ICMS próprio", "ICMS ST próprio", "DIFAL", "Antecipação", "ICMS ST Entradas", "FEM"]
CAMPOS_IMPOSTOS_MUNICIPAL = ["ISSQN a pagar", "ISSQN Retido (NF própria)"]
CAMPOS_RETENCOES_FEDERAL = ["CSRF (Retido)", "IRRF (Retido)", "INSS (Retido)", "ISSQN (Retido)"]