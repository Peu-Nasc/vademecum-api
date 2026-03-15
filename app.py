from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from google import genai
import os

app = Flask(__name__)
CORS(app) 

# --- FUNÇÃO DE BLINDAGEM MÁXIMA (NOVO) ---
# Tenta usar vários modelos caso um atinja o limite de taxa do Google
def chamar_ia_com_fallback(prompt):
    CHAVE_API = os.environ.get("GEMINI_API_KEY")
    cliente = genai.Client(api_key=CHAVE_API)
    
    # Lista de modelos baseada no seu painel (do maior limite para o menor)
    modelos_para_testar = [
        'gemini-3.1-flash-lite',  # 15 RPM
        'gemini-2.5-flash-lite',  # 10 RPM 
        'gemini-3-flash',         # 5 RPM
        'gemini-2.5-flash'        # 5 RPM
    ]

    for modelo in modelos_para_testar:
        try:
            print(f"[IA] Tentando conectar com o modelo: {modelo}")
            resposta = cliente.models.generate_content(
                model=modelo,
                contents=prompt
            )
            return resposta.text
        except Exception as e:
            print(f"[Aviso] Modelo {modelo} falhou ou atingiu o limite. Pulando para o próximo...")
            continue # Se der erro, tenta o próximo modelo da lista instantaneamente
            
    # Se TODOS os modelos falharem, retorna uma mensagem amigável sem quebrar o site
    return "### ⚠️ Professor Boog Sobrecarregado\nAu au! Estou farejando muitas leis ao mesmo tempo agora. Por favor, aguarde uns 30 segundinhos e tente pesquisar novamente!"


# --- FUNÇÃO 1: O BIBLIOTECÁRIO ---
def identificar_artigo_por_assunto(assunto, nome_lei):
    print(f"\n[IA Bibliotecária] Buscando o número do artigo para: {assunto}...")
    
    prompt = f"""
    Você é um assistente jurídico de busca. 
    Qual é o número exato do artigo principal na legislação '{nome_lei}' que trata sobre '{assunto}'? 
    Responda APENAS com o número inteiro em dígitos (ex: 121). Não escreva a palavra "Artigo", nem coloque ponto final.
    Se o assunto não existir nessa lei, responda 0.
    """
    
    # Usando o sistema blindado
    resposta_texto = chamar_ia_com_fallback(prompt)
    numero = re.sub(r'\D', '', resposta_texto)
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
        # O |$ garante que ele pegue o artigo até o final, mesmo se for o último da lei
        padrao_busca = f'({regex_atual}.*?)(?={regex_proximo}|$)'
        artigo_encontrado = re.search(padrao_busca, texto_lei, re.DOTALL | re.IGNORECASE)

        if artigo_encontrado:
            return artigo_encontrado.group(1).strip()
    return None


# --- FUNÇÃO 3: O PROFESSOR DIDÁTICO ---
def explicar_com_ia(texto_artigo, nome_lei, termo_busca):
    print(f"[IA Professor] Explicando o artigo...")
    
    prompt = f"""
    Você é o Professor Boog, o mascote bulldog e mentor jurídico desta plataforma.
    Seu tom de voz é amigável, encorajador, mas extremamente preciso e técnico quando necessário.
    Vá direto ao ponto, mas use expressões como "Dica do Boog" ou "Fique atento ao faro do Boog para pegadinhas".
    
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
    
    # Usando o sistema blindado
    return chamar_ia_com_fallback(prompt)


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
            'artigo_identificado': numero_artigo 
        })
    else:
        return jsonify({'sucesso': False, 'erro': f'Artigo {numero_artigo} não encontrado no sistema oficial.'})

if __name__ == '__main__':
    app.run(debug=True)