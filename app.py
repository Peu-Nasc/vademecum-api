from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from google import genai
import os

app = Flask(__name__)
CORS(app) 

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
        
        padrao_busca = f'({regex_atual}.*?)(?={regex_proximo}|$)'
        artigo_encontrado = re.search(padrao_busca, texto_lei, re.DOTALL | re.IGNORECASE)

        if artigo_encontrado:
            return artigo_encontrado.group(1).strip()
    return None

# ATUALIZAÇÃO: A função agora recebe o "termo_busca" exato do usuário
def explicar_com_ia(texto_artigo, nome_lei, termo_busca):
    print(f"\n[IA] Traduzindo o juridiquês do {nome_lei} para a busca: {termo_busca}")
    
    CHAVE_API = os.environ.get("GEMINI_API_KEY")
    cliente = genai.Client(api_key=CHAVE_API)
    
    # ATUALIZAÇÃO: Prompt "Sniper" para focar em parágrafos e incisos
    prompt = f"""
    Você é um professor de direito muito didático e focado em aprovação.
    A legislação pesquisada é: {nome_lei}.
    O usuário buscou especificamente por: "{termo_busca}".
    
    Aqui está o texto completo do Artigo correspondente:
    {texto_artigo}
    
    Sua missão:
    1. Se o usuário pediu um inciso (ex: I, II), alínea ou parágrafo (ex: § 1º) específico, foque sua explicação PRINCIPALMENTE nessa parte exata. Relacione-a com o "caput" (cabeça do artigo) apenas para dar contexto.
    2. Se ele buscou apenas o artigo de forma genérica, explique o artigo como um todo.
    3. Explique o que a norma significa em português simples e direto.
    4. Diga por que isso é importante (contexto prático).
    5. Aponte uma "pegadinha" comum que bancas de concurso ou OAB fazem com esse tema exato.
    """
    
    resposta = cliente.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    return resposta.text

# --- AS ROTAS DO SERVIDOR ---
@app.route('/')
def home():
    return jsonify({"status": "API do Vade Mecum Digital está online e operando! 🚀"})

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

    # ATUALIZAÇÃO: Extração inteligente do número do artigo
    # Tenta encontrar o número apenas se ele vier depois da palavra "Art" ou "Artigo"
    numero_match = re.search(r'(?:artigo|art\.?)\s*(\d+)', termo_busca, re.IGNORECASE)
    
    if numero_match:
        numero_artigo = int(numero_match.group(1))
    else:
        # Fallback: Se não achar a palavra "art", pega o primeiro número solto que encontrar
        numero_match_fallback = re.search(r'\d+', termo_busca)
        if numero_match_fallback:
            numero_artigo = int(numero_match_fallback.group(0))
        else:
            return jsonify({
                'sucesso': False,
                'erro': 'Por favor, digite o número do artigo que deseja buscar (ex: Artigo 5, Inciso XL).'
            })
        
    proximo_artigo = numero_artigo + 1
    
    regex_atual = rf'Art\.\s*{numero_artigo}[°º\.]?'
    regex_proximo = rf'Art\.\s*{proximo_artigo}[°º\.]?'
    
    texto_puro = capturar_artigo_planalto(url_alvo, regex_atual, regex_proximo)
    
    if texto_puro:
        # ATUALIZAÇÃO: Enviamos o termo_busca para a IA fazer a filtragem didática
        explicacao = explicar_com_ia(texto_puro, nome_da_lei, termo_busca)
        
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

if __name__ == '__main__':
    app.run(debug=True)
