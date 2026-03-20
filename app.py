from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from google import genai
import os
import traceback

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

@app.after_request
def add_cors_headers(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

def chamar_ia_com_fallback(prompt):
    CHAVE_API = os.environ.get("GEMINI_API_KEY")
    if not CHAVE_API: return "ERRO_SEM_CHAVE"
    try: cliente = genai.Client(api_key=CHAVE_API)
    except Exception as e: return f"ERRO_CLIENTE: {str(e)}"
    
    modelos_para_testar = ['gemini-3.1-flash-lite-preview', 'gemini-2.0-flash-lite', 'gemini-2.0-flash', 'gemini-2.5-flash']
    for modelo in modelos_para_testar:
        try:
            resposta = cliente.models.generate_content(model=modelo, contents=prompt)
            if resposta and hasattr(resposta, 'text') and resposta.text: return resposta.text
        except: continue 
    return "ERRO_IA_OCUPADA"

# --- O NOVO CÉREBRO OMNI-SEARCH DO BOOG ---
def identificar_lei_e_artigo(termo, categoria_escolhida):
    prompt = f"""
    Você é o bibliotecário jurídico chefe do Vade Mecum.
    O usuário digitou: "{termo}"
    E selecionou a categoria: "{categoria_escolhida}"
    
    REGRAS DE OURO:
    1. Se o usuário pesquisar um crime no Código Civil, CORRIJA para Código Penal (cp).
    2. Se pesquisar coisas civis no Penal, CORRIJA para Código Civil (cc).
    3. Se ele escolheu "Leis Especiais", descubra se é Maria da Penha (lmp), ECA (eca), CLT (clt) ou a nova Lei Felca/ECA Digital (ecadigital).
    4. ANTI-ALUCINAÇÃO: Se o usuário digitar piadas ou termos sem sentido, responda EXATAMENTE: erro|0.
    5. LEI COMPLETA: Se o usuário digitar APENAS o nome da lei (ex: "lei felca", "maria da penha", "codigo penal") sem especificar assunto ou artigo, retorne a chave e a palavra COMPLETA (ex: ecadigital|COMPLETA ou lmp|COMPLETA).
    
    Chaves permitidas: cdc, cc, cf, cp, lmp, eca, clt, ecadigital.
    
    Responda APENAS no formato: chave|numero
    Exemplo: cp|157 ou ecadigital|COMPLETA
    Se não existir, responda: erro|0
    """
    res = chamar_ia_com_fallback(prompt)
    if "ERRO" in res: return "erro", "0"
    
    match = re.search(r'(cdc|cc|cf|cp|lmp|eca|clt|ecadigital)\|(\d+(?:-[a-zA-Z]|[a-zA-Z])?|completa)', res.lower())
    if match:
        chave = match.group(1)
        artigo = match.group(2).upper()
        if artigo != "COMPLETA" and not '-' in artigo and re.search(r'[A-Z]', artigo):
            artigo = re.sub(r'([A-Z])', r'-\1', artigo)
        return chave, artigo
    return "erro", "0"

def capturar_artigo_planalto(url, regex_atual, regex_proximo):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        resposta = requests.get(url, headers=headers, timeout=10)
        resposta.encoding = 'iso-8859-1'
        if resposta.status_code == 200:
            soup = BeautifulSoup(resposta.text, 'html.parser')
            for strike in soup.find_all('strike'): strike.decompose()
            texto_lei = soup.get_text(separator=' \n ')
            
            if regex_proximo:
                padrao_busca = f'({regex_atual}.*?)(?={regex_proximo}|$)'
            else:
                # Se não tem limite, copia do Art 1º até ao final do site!
                padrao_busca = f'({regex_atual}.*)'
                
            artigo_encontrado = re.search(padrao_busca, texto_lei, re.DOTALL)
            
            if artigo_encontrado: 
                texto_final = artigo_encontrado.group(1).strip()
                # TRAVA DE SEGURANÇA GÊNIAL: Protege o seu site de travar com leis infinitas.
                if len(texto_final) > 15000:
                    texto_final = texto_final[:15000] + "\n\n[... O texto da lei é muito extenso e continua. Para ler artigos específicos, pesquise pelo número do artigo ou termo desejado.]"
                return texto_final
        return None
    except: return None

def explicar_com_ia(texto_artigo, nome_lei, termo_busca):
    # Voltámos ao prompt original de sucesso, mas avisando a IA que pode ser uma lei inteira.
    prompt = f"""
    Você é o Professor Boog, o mascote bulldog e mentor jurídico. Vá direto ao ponto.
    Lei: {nome_lei} | Busca do Usuário: {termo_busca}
    Texto Oficial: {texto_artigo}
    
    Se o Texto Oficial for de uma lei inteira, explique a lei toda de forma brilhante. Se for um artigo único, explique o artigo.
    
    Responda ESTRITAMENTE neste formato Markdown:
    ### 📖 O que significa?
    ### 🎯 Aplicação Prática
    ### ⚠️ Pegadinha de Prova
    """
    return chamar_ia_com_fallback(prompt)

@app.route('/')
def home(): return jsonify({"status": "API Vade Mecum Online! 🚀"})

@app.route('/api/buscar', methods=['POST', 'OPTIONS'])
def buscar_artigo():
    if request.method == 'OPTIONS': return jsonify({'status': 'ok'}), 200
    try:
        dados = request.json
        termo_busca = dados.get('termo', '')
        lei_escolhida = dados.get('lei', 'cdc') 
        
        urls_governo = {
            'cdc': 'https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm',
            'cc': 'https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm',
            'cf': 'https://www.planalto.gov.br/ccivil_03/constituicao/constituicaocompilado.htm',
            'cp': 'https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm',
            'lmp': 'https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11340.htm',
            'eca': 'https://www.planalto.gov.br/ccivil_03/leis/l8069.htm',
            'clt': 'https://www.planalto.gov.br/ccivil_03/decreto-lei/del5452.htm',
            'ecadigital': 'https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/lei/L15211.htm'
        }
        nomes_leis = {
            'cdc': 'Código de Defesa do Consumidor',
            'cc': 'Código Civil',
            'cf': 'Constituição Federal do Brasil',
            'cp': 'Código Penal',
            'lmp': 'Lei Maria da Penha',
            'eca': 'Estatuto da Criança e do Adolescente',
            'clt': 'Consolidação das Leis do Trabalho',
            'ecadigital': 'ECA Digital (Lei Felca - Lei 15.211/25)'
        }
        
        eh_apenas_numero = False
        numero_extraido = ""
        numero_match = re.search(r'(?:artigo|art\.?)\s*(\d+(?:-[A-Za-z]|[A-Za-z])?)', termo_busca, re.IGNORECASE)
        if numero_match:
            numero_extraido = numero_match.group(1).upper()
            eh_apenas_numero = True
        elif re.match(r'^\d+(?:-[A-Za-z]|[A-Za-z])?$', termo_busca.strip()): 
            numero_extraido = termo_busca.strip().upper()
            eh_apenas_numero = True

        if eh_apenas_numero and lei_escolhida != 'especiais':
            chave_lei = lei_escolhida
            numero_artigo = numero_extraido
        else:
            nome_da_lei_dropdown = "Leis Especiais" if lei_escolhida == 'especiais' else nomes_leis.get(lei_escolhida, '')
            chave_lei, numero_artigo = identificar_lei_e_artigo(termo_busca, nome_da_lei_dropdown)
            
            if chave_lei == "erro" or numero_artigo == "0":
                return jsonify({'sucesso': False, 'erro': f'Não encontrámos a lei exata para "{termo_busca}".'})
                
        if not '-' in numero_artigo and re.search(r'[A-Z]', numero_artigo) and numero_artigo != "COMPLETA":
            numero_artigo = re.sub(r'([A-Z])', r'-\1', numero_artigo)
            
        url_alvo = urls_governo.get(chave_lei)
        nome_da_lei = nomes_leis.get(chave_lei)
        
        # A MÁGICA DE PUXAR A LEI TODA ACONTECE AQUI
        if numero_artigo == "COMPLETA":
            regex_atual = r'(?:\n|^)\s*Art\.\s*1[°º\.]?(?!\d|-|[A-Z])'
            regex_proximo = None # A ausência de limite faz ele ler a lei toda
        else:
            regex_atual = rf'(?:\n|^)\s*Art\.\s*{numero_artigo}[°º\.]?(?!\d|-|[A-Z])'
            regex_proximo = r'(?:\n|^)\s*Art\.\s*\d+'
            
        texto_puro = capturar_artigo_planalto(url_alvo, regex_atual, regex_proximo)
        
        if texto_puro:
            explicacao = explicar_com_ia(texto_puro, nome_da_lei, termo_busca)
            return jsonify({
                'sucesso': True,
                'lei_seca': texto_puro,
                'explicacao_ia': explicacao,
                'artigo_identificado': numero_artigo if numero_artigo != "COMPLETA" else "Toda a Lei",
                'nome_lei_corrigido': nome_da_lei
            })
        else:
            return jsonify({'sucesso': False, 'erro': f'Conteúdo não encontrado em {nome_da_lei}.'})
            
    except Exception as e:
        print(f"[ERRO CRÍTICO] {traceback.format_exc()}")
        return jsonify({'sucesso': False, 'erro': f'ERRO: {str(e)}'})

if __name__ == '__main__':
    app.run(debug=True)