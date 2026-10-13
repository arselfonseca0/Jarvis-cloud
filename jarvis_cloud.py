import os
import time
import datetime
import requests  
import feedparser 
import imaplib  
import email
from email.header import decode_header
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading

# A biblioteca para criar o Servidor Fantasma
from flask import Flask

from google import genai
from google.genai import types

# ==========================================
# AS TUAS CHAVES MESTRAS (AGORA INVISÍVEIS)
# O código vai buscá-las ao cofre do Render!
# ==========================================
CHAVE_API_GEMINI = os.environ.get("GEMINI_KEY")
EMAIL_CONTA = os.environ.get("EMAIL_USER")
CHAVE_APP = os.environ.get("EMAIL_PASS")
CHAVE_TELEGRAM = os.environ.get("TELEGRAM_KEY")

# Só arranca a IA se a chave for encontrada no cofre
if CHAVE_API_GEMINI:
    client = genai.Client(api_key=CHAVE_API_GEMINI)

modelos_ia = ["gemini-2.0-flash", "gemini-1.5-flash"]

# ==========================================
# IDENTIDADE E INSTRUÇÕES
# ==========================================
nome = "Arsel"
escola = "Colégio de Gaia"

def obter_configuracao():
    dias_semana = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
    data_hoje = f"{dias_semana[datetime.datetime.now().weekday()]}, {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"
    instrucoes = f"""
    És o Jarvis, o assistente pessoal e amigo de confiança do {nome} (um jovem de 18 anos, estudante de Eletrónica no {escola}).
    Fala de forma descontraída, inteligente e perspicaz. Responde sempre em português de Portugal.
    NÃO uses emojis nem formatações (* ou **). Mantém frases curtas. Não fales da PAP a não ser que ele puxe o assunto.
    Data de hoje: {data_hoje}. 

    REGRAS DE AÇÃO:
    1. TAREFAS: Usa [CRIAR_TAREFA] + texto para adicionar.
    2. EMAILS: Usa [ENVIAR_EMAIL] email_do_destino | assunto | corpo do texto
    3. CONVERSA: Para o resto, responde normalmente sem tags.
    """
    return types.GenerateContentConfig(system_instruction=instrucoes, temperature=0.7)

# ==========================================
# HABILIDADES NATIVAS (ESCUDO LOCAL)
# ==========================================
def obter_clima():
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=41.13&longitude=-8.61&current=temperature_2m,wind_speed_10m&timezone=Europe%2FLisbon"
        resposta = requests.get(url).json()
        return f"Chefe, os satélites indicam que estão {resposta['current']['temperature_2m']} graus, com ventos de {resposta['current']['wind_speed_10m']} km/h."
    except:
        return "Perdi a ligação aos satélites meteorológicos."

def obter_noticias():
    try:
        feed = feedparser.parse("https://www.rtp.pt/noticias/rss")
        resposta = "Aqui estão as manchetes de hoje, chefe. "
        for i in range(3):
            resposta += f"Tópico {i+1}: {feed.entries[i].title}. "
        return resposta
    except:
        return "Os canais de informação estão bloqueados."

def verificar_emails():
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL_CONTA, CHAVE_APP)
        mail.select("inbox")
        _, mensagens = mail.search(None, "UNSEEN")
        ids_emails = mensagens[0].split()
        
        if not ids_emails:
            mail.logout()
            return "Caixa de entrada limpa, chefe. Sem mensagens novas."
            
        resposta = f"Tens {len(ids_emails)} mensagens não lidas. Eis as 3 mais recentes. "
        for id_email in reversed(ids_emails[-3:]):
            _, msg_data = mail.fetch(id_email, "(RFC822)")
            for parte in msg_data:
                if isinstance(parte, tuple):
                    msg = email.message_from_bytes(parte[1])
                    assunto, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(assunto, bytes):
                        assunto = assunto.decode(encoding if encoding else "utf-8")
                    remetente = msg.get("From").split('<')[0].strip()
                    resposta += f"De {remetente}: sobre {assunto}. "
        mail.logout()
        return resposta
    except Exception as e:
        return f"Falha na leitura do correio: {e}"

def enviar_email(destinatario, assunto, corpo):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONTA
        msg['To'] = destinatario
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo, 'plain'))
        servidor = smtplib.SMTP('smtp.gmail.com', 587)
        servidor.starttls()
        servidor.login(EMAIL_CONTA, CHAVE_APP)
        servidor.send_message(msg)
        servidor.quit()
        return f"Email enviado com sucesso para {destinatario}."
    except Exception as e:
        return f"Falha ao disparar o email: {e}"

# ==========================================
# CÉREBRO PRINCIPAL (PROCESSAMENTO DE IA)
# ==========================================
def processar_ia(tarefa):
    print(f"[JARVIS] A processar ordem: {tarefa}")
    tarefa_min = tarefa.lower()
    
    if any(g in tarefa_min for g in ["tempo", "clima", "chover", "graus", "temperatura"]):
        return obter_clima()
    elif any(g in tarefa_min for g in ["notícias", "noticias", "manchetes", "mundo"]):
        return obter_noticias()
    elif any(g in tarefa_min for g in ["lê os meus emails", "mensagens novas", "ver o correio"]):
        return verificar_emails()
    
    texto_final = None
    ultimo_erro = None
    
    for modelo in modelos_ia:
        try:
            print(f"[JARVIS] A tentar usar o modelo {modelo}...")
            chat_modelo = client.chats.create(model=modelo, config=obter_configuracao())
            resposta = chat_modelo.send_message(tarefa)
            texto_ia = resposta.text
            
            if "[CRIAR_TAREFA]" in texto_ia:
                tarefa_limpa = texto_ia.replace("[CRIAR_TAREFA]", "").strip()
                with open("tarefas.txt", "a", encoding="utf-8") as f:
                    f.write(f"• {tarefa_limpa}\n")
                texto_final = "Tarefa adicionada à base de dados na nuvem, chefe."
            elif "[ENVIAR_EMAIL]" in texto_ia:
                dados = texto_ia.replace("[ENVIAR_EMAIL]", "").strip().split("|")
                if len(dados) == 3:
                    texto_final = enviar_email(dados[0].strip(), dados[1].strip(), dados[2].strip())
                else:
                    texto_final = "Faltam dados para enviar o email."
            else:
                texto_final = texto_ia
            break 
        except Exception as e:
            ultimo_erro = e
            time.sleep(1)
            
    if not texto_final:
        return f"[Erro de Conexão na Nuvem: {ultimo_erro}]"
        
    return texto_final

# ==========================================
# LOOP DO TELEGRAM (RADAR)
# ==========================================
def radar_telegram():
    print("[RADAR] Sistema de interceção do Telegram online...")
    offset = None
    while True:
        try:
            if CHAVE_TELEGRAM:
                url = f"https://api.telegram.org/bot{CHAVE_TELEGRAM}/getUpdates"
                params = {"timeout": 10, "offset": offset}
                resposta = requests.get(url, params=params).json()
                
                if resposta.get("ok") and resposta.get("result"):
                    for mensagem in resposta["result"]:
                        offset = mensagem["update_id"] + 1
                        if "message" in mensagem and "text" in mensagem["message"]:
                            texto = mensagem["message"]["text"]
                            chat_id = mensagem["message"]["chat"]["id"]
                            
                            print(f"\n[IPHONE] Recebido: {texto}")
                            resposta_jarvis = processar_ia(texto)
                            print(f"[JARVIS] Resposta: {resposta_jarvis}")
                            
                            url_enviar = f"https://api.telegram.org/bot{CHAVE_TELEGRAM}/sendMessage"
                            requests.post(url_enviar, data={"chat_id": chat_id, "text": resposta_jarvis})
        except Exception as e:
            pass
        time.sleep(1.5)

# ==========================================
# SERVIDOR WEB FANTASMA (PARA O RENDER)
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>A MÁQUINA ESTÁ VIVA. JARVIS CLOUD ONLINE E A ESCUTAR.</h1>"

def iniciar_servidor_web():
    # O Render exige que o servidor procure a porta do sistema
    porta = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=porta)

if __name__ == "__main__":
    # Arranca o Radar do Telegram em segundo plano (Thread invisível)
    threading.Thread(target=radar_telegram, daemon=True).start()
    
    # Arranca o site fantasma em primeiro plano (impede que o código morra)
    iniciar_servidor_web()