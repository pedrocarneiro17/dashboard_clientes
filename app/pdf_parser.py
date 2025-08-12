# app/pdf_parser.py
import pdfplumber
import re

def extrair_dados_pdf(pdf_file_stream):
    """
    Extrai dados da folha de pagamento de um stream de arquivo PDF.
    """
    texto_completo = ""
    try:
        with pdfplumber.open(pdf_file_stream) as pdf:
            for pagina in pdf.pages:
                texto_da_pagina = pagina.extract_text(x_tolerance=2, y_tolerance=2)
                if texto_da_pagina:
                    texto_completo += texto_da_pagina + "\n"
    except Exception as e:
        return {"erro": f"Não foi possível ler o arquivo PDF: {e}"}

    dados = {
        "CNPJ": None, "PERIODO": None, "SITUACAO_COLABORADORES": None, "COLABORADORES": [],
        "LIQUIDO_COLABORADORES": None, "LIQUIDO_EMPREGADORES": None, "VALOR_GPS": None,
        "VALOR_GFD_MENSAL": None, "VALOR_GFD_RESCISORIA": None
    }
    
    mapa_meses = {
        "JANEIRO": "01", "FEVEREIRO": "02", "MARÇO": "03", "ABRIL": "04",
        "MAIO": "05", "JUNHO": "06", "JULHO": "07", "AGOSTO": "08",
        "SETEMBRO": "09", "OUTUBRO": "10", "NOVEMBRO": "11", "DEZEMBRO": "12"
    }
    match_periodo = re.search(r"referente ao mês de (\w+)/(\d{4})", texto_completo, re.IGNORECASE)
    if match_periodo:
        mes_nome = match_periodo.group(1).upper()
        ano = match_periodo.group(2)
        mes_num = mapa_meses.get(mes_nome)
        if mes_num:
            dados["PERIODO"] = f"{ano}-{mes_num}"

    linhas = texto_completo.split('\n')
    for i, linha in enumerate(linhas):
        if "Admissão em" in linha:
            partes = linha.split("Admissão em")
            nome_limpo = re.sub(r'^\d+\s+', '', partes[0]).strip()
            nome_limpo = re.sub(r'\s+[\d\s]+$', '', nome_limpo).strip()
            match_data = re.search(r'(\d{2}/\d{2}/\d{4})', partes[1])
            if nome_limpo and match_data:
                data_admissao = match_data.group(1)
                proxima_linha = linhas[i + 1] if i + 1 < len(linhas) else ""
                if len(proxima_linha.strip().split()) <= 3 and proxima_linha and "Pró-Labore" not in proxima_linha:
                    nome_limpo = f"{nome_limpo} {proxima_linha.strip()}"
                    contexto_seguinte = "\n".join(linhas[i + 2:min(i + 12, len(linhas))])
                else:
                    contexto_seguinte = "\n".join(linhas[i + 1:min(i + 11, len(linhas))])
                if "Pró-Labore" not in contexto_seguinte:
                    dados["COLABORADORES"].append({"nome": nome_limpo, "admissao": data_admissao})

    match_cnpj = re.search(r"CNPJ:(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", texto_completo)
    if match_cnpj: dados["CNPJ"] = match_cnpj.group(1).strip()
    match_situacao = re.search(r"Ativos: \d+.*(?:Doença|Outras sit\.): \d+", texto_completo)
    if match_situacao: dados["SITUACAO_COLABORADORES"] = match_situacao.group(0).strip()
    
    match_liquido = re.search(r"^L[íi]quido\s+[\d\.,]+\s+([\d\.,]+)\s+([\d\.,]+)", texto_completo, re.MULTILINE | re.IGNORECASE)
    if match_liquido:
        dados["LIQUIDO_COLABORADORES"] = match_liquido.group(1).strip()
        dados["LIQUIDO_EMPREGADORES"] = match_liquido.group(2).strip()

    impostos_encontrados = {}
    for match in re.finditer(r"^(GPS|GFD Mensal|GFD Rescisória)\s+R\$\s+([\d\.,]+)", texto_completo, re.MULTILINE):
        impostos_encontrados[match.group(1).strip()] = f"R$ {match.group(2).strip()}"
    dados["VALOR_GPS"] = impostos_encontrados.get("GPS", "Não encontrado")
    dados["VALOR_GFD_MENSAL"] = impostos_encontrados.get("GFD Mensal", "Não encontrado")
    dados["VALOR_GFD_RESCISORIA"] = impostos_encontrados.get("GFD Rescisória", "Não encontrado")
    
    return dados
