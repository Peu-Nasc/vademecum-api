from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from google import genai

# 1. INICIALIZANDO O SERVIDOR FLASK
app = Flask(__name__)
CORS(app) # <-- NOVA LINHA AQUI (Isso libera o GitHub para conversar com o Render)

# --- O MOTOR DE BUSCA (BACK-END) ---
def capturar_artigo_planalto(url, regex_atual, regex_proximo):
    print(f"Iniciando raspagem de dados no link: {url}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    resposta = requests.get(url, headers=headers)
    
    resposta.encoding = 'iso-8859-1'

    if resposta.status_code == 200:
        soup = BeautifulSoup(resposta.text, 'html.parser')
        
        for strike in soup.find_all('strike'):
            strike.decompose()

        texto_lei = soup.get_text(separator='\n')
        
        # A MÁGICA AQUI: Adicionamos o |$ no final do padrao_busca
        padrao_busca = f'({regex_atual}.*?)(?={regex_proximo}|$)'
        artigo_encontrado = re.search(padrao_busca, texto_lei, re.DOTALL | re.IGNORECASE)

        if artigo_encontrado:
            return artigo_encontrado.group(1).strip()
    return None


def explicar_com_ia(texto_artigo, nome_lei):
    print(f"\n[IA] Traduzindo o juridiquês do {nome_lei}...")
    
    # IMPORTANTE: Insira sua NOVA chave de API aqui
    CHAVE_API = "AIzaSyDf2ytHL6rTQJtLJOtWhkAXxTifDLVS_4E"
    cliente = genai.Client(api_key=CHAVE_API)
    
    prompt = f"""
    Você é um professor de direito muito didático e focado em aprovação.
    Leia o artigo abaixo, que pertence à legislação: {nome_lei}.
    Faça o seguinte:
    1. Explique o que ele significa em português simples e direto.
    2. Diga por que ele é importante (contexto prático).
    3. Aponte uma "pegadinha" comum que bancas de concurso ou OAB fazem com esse artigo.
    
    Artigo:
    {texto_artigo}
    """
    
    resposta = cliente.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    return resposta.text


# --- AS ROTAS DO SERVIDOR (A PONTE FLASK) ---

@app.route('/')
def home():
    # Renderiza o rosto do site
    return render_template('index.html')


@app.route('/api/buscar', methods=['POST'])
def buscar_artigo():
    dados = request.json
    termo_busca = dados.get('termo', '')
    lei_escolhida = dados.get('lei', 'cdc') # Recebe a lei escolhida no dropdown
    
    # Dicionário de URLs Oficiais do Planalto
    # Dicionário de URLs Oficiais do Planalto
    urls_governo = {
        'cdc': 'https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm',
        'cc': 'https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm',
        'cf': 'https://www.planalto.gov.br/ccivil_03/constituicao/constituicaocompilado.htm',
        'cp': 'https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm' # NOVA LINHA AQUI
    }
    
    nomes_leis = {
        'cdc': 'Código de Defesa do Consumidor',
        'cc': 'Código Civil',
        'cf': 'Constituição Federal do Brasil',
        'cp': 'Código Penal' # NOVA LINHA AQUI
    }
    
    url_alvo = urls_governo.get(lei_escolhida)
    nome_da_lei = nomes_leis.get(lei_escolhida)

    # Extraindo apenas o número do que o usuário digitou (ex: "Artigo 5" vira "5")
    numero_match = re.search(r'\d+', termo_busca)
    
    if not numero_match:
        return jsonify({
            'sucesso': False,
            'erro': 'Por favor, digite o número do artigo que deseja buscar (ex: Artigo 5).'
        })
        
    numero_artigo = int(numero_match.group(0))
    proximo_artigo = numero_artigo + 1
    
    # Criando a lógica flexível de busca (aceita Art. 1º, Art. 10., etc)
    regex_atual = rf'Art\.\s*{numero_artigo}[°º\.]?'
    regex_proximo = rf'Art\.\s*{proximo_artigo}[°º\.]?'
    
    # Chamando a raspagem
    texto_puro = capturar_artigo_planalto(url_alvo, regex_atual, regex_proximo)
    
    if texto_puro:
        # Passando para a IA gerar a explicação
        explicacao = explicar_com_ia(texto_puro, nome_da_lei)
        
        return jsonify({
            'sucesso': True,
            'lei_seca': texto_puro,
            'explicacao_ia': explicacao
        })
    else:
        return jsonify({
            'sucesso': False,
            'erro': f'Não conseguimos encontrar o Artigo {numero_artigo} na legislação selecionada.'
        })

# --- LIGANDO O MOTOR ---
if __name__ == '__main__':
    app.run(debug=True)