from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from google import genai
import os
import traceback # Biblioteca para rastrear o erro exato

app = Flask(__name__)
CORS(app) 

# --- FUNÇÃO DE BLINDAGEM MÁXIMA ---
def chamar_ia_com_fallback(prompt):
    CHAVE_API = os.environ.get("GEMINI_API_KEY")
    if not CHAVE_API:
        return "ERRO_SEM_CHAVE"
        
    try:
        cliente = genai.Client(api_key=CHAVE_API)
    except Exception as e:
        return f"ERRO_CLIENTE: {str(e)}"
    
    modelos_para_testar = [
        'gemini-3.1-flash-lite-preview',
        'gemini-2.0-flash-lite',
        'gemini-2.0-flash',
        'gemini-2.5-flash'
    ]

    for modelo in modelos_para_testar:
        try:
            print(f"[IA] A tentar: {modelo}")
            resposta = cliente.models.generate_content(
                model=modelo,
                contents=prompt
            )
            if resposta and resposta.text:
                return resposta.text
        except Exception as e:
            print(f"[Aviso] Modelo {modelo} falhou: {e}")
            continue 
            
    return "ERRO_IA_OCUPADA"

# --- FUNÇÃO 1: O BIBLIOTECÁRIO ---
def identificar_artigo_por_assunto(assunto, nome_lei):
    prompt = f"Qual é o número exato do artigo principal na legislação '{nome_lei}' que trata sobre '{assunto}'? Responda APENAS com o número inteiro em dígitos."
    resposta_texto = chamar_ia_com_fallback(prompt)
    
    if "ERRO" in resposta_texto:
        return -1 # Código secreto para falha da IA
        
    numeros = re.findall(r'\d+', resposta_texto)
    return int(numeros[0]) if numeros else 0

# --- FUNÇÃO 2: O RASPADOR OFICIAL ---
def capturar_artigo_planalto(url, regex_atual, regex_proximo):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        # Adicionamos um timeout para não travar se o site do governo cair
        resposta = requests.get(url, headers=headers, timeout=10)
        resposta.encoding = 'iso-8859-1'
        if resposta.status_code == 200:
            soup = BeautifulSoup(resposta.text, 'html.parser')
            for strike in soup.find_all('strike'):
                strike.decompose()

            texto_lei = soup.get_text(separator='\n')
            padrao_busca = f'({regex_atual}.*?)(?={regex_proximo}|$)'
            artigo_encontrado = re.search(padrao_busca, texto_lei, re.DOTALL | re.IGNORECASE)

            if artigo_encontrado:
                return artigo_encontrado.group(1).strip()
        return None
    except Exception as e:
        print(f"Erro ao conectar com o site do governo: {e}")
        return None

# --- FUNÇÃO 3: O PROFESSOR DIDÁTICO ---
def explicar_com_ia(texto_artigo, nome_lei, termo_busca):
    prompt = f"""
    Você é o Professor Boog, o mascote bulldog e mentor jurídico.
    Vá direto ao ponto.
    
    Lei: {nome_lei} | Busca: {termo_busca}
    Texto: {texto_artigo}
    
    Responda ESTRITAMENTE neste formato Markdown:
    ### 📖 O que significa?
    ### 🎯 Aplicação Prática
    ### ⚠️ Pegadinha de Prova
    """
    res = chamar_ia_com_fallback(prompt)
    if "ERRO" in res:
        return "### ⚠️ Professor Boog Sobrecarregado\nAu au! O meu faro está cansado. As inteligências artificiais do Google estão no limite de uso. Tente novamente em 1 minuto!"
    return res

# --- AS ROTAS DO SERVIDOR ---
@app.route('/')
def home():
    return jsonify({"status": "API Vade Mecum Online! 🚀"})

@app.route('/api/buscar', methods=['POST'])
def buscar_artigo():
    # O TRY-EXCEPT GIGANTE QUE VAI SALVAR A NOSSA VIDA
    try:
        dados = request.json
        termo_busca = dados.get('termo', '')
        lei_escolhida = dados.get('lei', 'cdc') 
        
        urls_governo = {
            'cdc': 'https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm',
            'cc': 'https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm',
            'cf': 'https://www.planalto.gov.br/ccivil_03/constituicao/constituicaocompilado.htm',
            'cp': 'https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm' 
        }
        nomes_leis = {
            'cdc': 'Código de Defesa do Consumidor',
            'cc': 'Código Civil',
            'cf': 'Constituição Federal do Brasil',
            'cp': 'Código Penal' 
        }
        
        url_alvo = urls_governo.get(lei_escolhida)
        nome_da_lei = nomes_leis.get(lei_escolhida)

        numero_match = re.search(r'(?:artigo|art\.?)\s*(\d+)', termo_busca, re.IGNORECASE)
        
        if numero_match:
            numero_artigo = int(numero_match.group(1))
        elif termo_busca.isdigit(): 
            numero_artigo = int(termo_busca)
        else:
            numero_artigo = identificar_artigo_por_assunto(termo_busca, nome_da_lei)
            
            if numero_artigo == -1:
                return jsonify({'sucesso': False, 'erro': 'A Chave da API sumiu do Render ou os modelos falharam. Verifique os Logs do Render.'})
            if numero_artigo == 0:
                return jsonify({'sucesso': False, 'erro': f'Não encontrámos um artigo para "{termo_busca}".'})
            
        proximo_artigo = numero_artigo + 1
        regex_atual = rf'Art\.\s*{numero_artigo}[°º\.]?'
        regex_proximo = rf'Art\.\s*{proximo_artigo}[°º\.]?'
        
        texto_puro = capturar_artigo_planalto(url_alvo, regex_atual, regex_proximo)
        
        if texto_puro:
            explicacao = explicar_com_ia(texto_puro, nome_da_lei, termo_busca)
            return jsonify({
                'sucesso': True,
                'lei_seca': texto_puro,
                'explicacao_ia': explicacao,
                'artigo_identificado': numero_artigo 
            })
        else:
            return jsonify({'sucesso': False, 'erro': f'Artigo {numero_artigo} não encontrado. O site do governo pode estar fora do ar ou o artigo não existe.'})
            
    except Exception as e:
        # SE ALGO CRASHAR, ELE MOSTRA O ERRO EXATO NO SITE
        erro_real = str(e)
        print(f"[ERRO CRÍTICO NO CÓDIGO] {traceback.format_exc()}")
        return jsonify({'sucesso': False, 'erro': f'ERRO DETECTADO NO PYTHON: {erro_real}'})

if __name__ == '__main__':
    app.run(debug=True)
