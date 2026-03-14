from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from google import genai
import os

app = Flask(__name__)
CORS(app) 

# --- FUNÇÃO 1: O BIBLIOTECÁRIO (NOVO) ---
def identificar_artigo_por_assunto(assunto, nome_lei):
    print(f"\n[IA Bibliotecária] Buscando o número do artigo para: {assunto}...")
    CHAVE_API = os.environ.get("GEMINI_API_KEY")
    cliente = genai.Client(api_key=CHAVE_API)
    
    prompt = f"""
    Você é um assistente jurídico de busca. 
    Qual é o número exato do artigo principal na legislação '{nome_lei}' que trata sobre '{assunto}'? 
    Responda APENAS com o número inteiro em dígitos (ex: 121). Não escreva a palavra "Artigo", nem coloque ponto final.
    Se o assunto não existir nessa lei, responda 0.
    """
    
    resposta = cliente.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    # Pega apenas os números da resposta da IA
    numero = re.sub(r'\D', '', resposta.text)
    return int(numero) if numero else 0

# --- FUNÇÃO 2: O RASPADOR OFICIAL ---
def capturar_artigo_planalto(url, regex_atual, regex_proximo):
    headers = {'User-Agent': 'Mozilla/5.0'}
    resposta = requests.get(url, headers=headers)
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

# --- FUNÇÃO 3: O PROFESSOR DIDÁTICO ---
def explicar_com_ia(texto_artigo, nome_lei, termo_busca):
    print(f"[IA Professor] Explicando o artigo...")
    CHAVE_API = os.environ.get("GEMINI_API_KEY")
    cliente = genai.Client(api_key=CHAVE_API)
    
    prompt = f"""
    Você é um professor de direito direto ao ponto. SEM SAUDAÇÕES.
    
    Legislação: {nome_lei}.
    Busca do usuário: "{termo_busca}".
    Texto: {texto_artigo}
    
    Responda ESTRITAMENTE neste formato Markdown:
    
    ### 📖 O que significa?
    (Explique a lei ou o tema em 1 ou 2 parágrafos curtos e muito claros. Sem juridiquês).
    
    ### 🎯 Aplicação Prática
    (Explique a importância no mundo real. Use obrigatoriamente "bullet points" curtos).
    
    ### ⚠️ Pegadinha de Prova
    (Aponte a principal armadilha das bancas de concurso).
    """
    
    resposta = cliente.models.generate_content(model='gemini-2.5-flash', contents=prompt)
    return resposta.text

# --- AS ROTAS DO SERVIDOR ---
@app.route('/')
def home():
    return jsonify({"status": "API do Vade Mecum Digital está online! 🚀"})

@app.route('/api/buscar', methods=['POST'])
def buscar_artigo():
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

    # 1. TENTA ACHAR NÚMERO NA BUSCA (ex: "Artigo 121")
    numero_match = re.search(r'(?:artigo|art\.?)\s*(\d+)', termo_busca, re.IGNORECASE)
    
    if numero_match:
        numero_artigo = int(numero_match.group(1))
    elif termo_busca.isdigit(): # Se o usuário digitou só "121"
        numero_artigo = int(termo_busca)
    else:
        # 2. SE FOR UMA PALAVRA (ex: "feminicidio"), CHAMA A IA BIBLIOTECÁRIA
        numero_artigo = identificar_artigo_por_assunto(termo_busca, nome_da_lei)
        if numero_artigo == 0:
            return jsonify({'sucesso': False, 'erro': f'Não encontramos um artigo específico para "{termo_busca}" nesta lei.'})
        
    proximo_artigo = numero_artigo + 1
    regex_atual = rf'Art\.\s*{numero_artigo}[°º\.]?'
    regex_proximo = rf'Art\.\s*{proximo_artigo}[°º\.]?'
    
    # 3. RASPA A LEI OFICIAL
    texto_puro = capturar_artigo_planalto(url_alvo, regex_atual, regex_proximo)
    
    if texto_puro:
        # 4. EXPLICA COM A IA PROFESSORA
        explicacao = explicar_com_ia(texto_puro, nome_da_lei, termo_busca)
        return jsonify({
            'sucesso': True,
            'lei_seca': texto_puro,
            'explicacao_ia': explicacao,
            'artigo_identificado': numero_artigo # Retorna o número que a IA encontrou para mostrar na tela
        })
    else:
        return jsonify({'sucesso': False, 'erro': f'Artigo {numero_artigo} não encontrado no sistema oficial.'})

if __name__ == '__main__':
    app.run(debug=True)