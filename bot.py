import telebot
import requests
import os
import json
import base64
from github import Github, Auth

# ----------------- CREDENCIALES -----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("TOKEN_GITHUB")

# ✅ Usamos v1beta para que 'systemInstruction' funcione, pero con el modelo base
GEMINI_MODEL = "gemini-1.5-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ----------------- GITHUB SETUP -----------------
auth = Auth.Token(GITHUB_TOKEN)
gh = Github(auth=auth)
repo_name = "josebernardinogonza-pixel/telegram-ai-bot-pro"
repo = gh.get_repo(repo_name)

# ----------------- SYSTEM PROMPT -----------------
SYSTEM_PROMPT = """
Actúa como "QuantBet AI", un modelo de análisis cuantitativo deportivo.
Tu objetivo es identificar ineficiencias en las cuotas y generar pronósticos (+EV).
Usa métricas como xG, Distribución de Poisson y Fracción de Kelly (1/8).
Formato: Markdown profesional con emojis (📊, 💰).
"""

@bot.message_handler(commands=['start'])
def start(message):
    welcome_msg = "📊 **QuantBet AI Online**. Envía un partido o imagen de cuotas para analizar."
    bot.reply_to(message, welcome_msg, parse_mode="Markdown")

@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_message(message):
    bot.send_chat_action(message.chat.id, 'typing')
    
    user_prompt = message.text or message.caption or "Realiza un análisis predictivo."
    parts = [{"text": user_prompt}]

    if message.photo:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        base64_image = base64.b64encode(downloaded).decode('utf-8')
        parts.append({
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": base64_image
            }
        })

    # Estructura de Payload compatible con v1beta
    payload = {
        "systemInstruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": [{
            "role": "user",
            "parts": parts
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048
        }
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        result = response.json()
        
        if "error" in result:
            # Si v1beta falla por el nombre del modelo, intentamos un fallback rápido
            bot.reply_to(message, f"⚠️ Error de API: {result['error']['message']}")
            return
            
        ai_reply = result["candidates"][0]["content"]["parts"][0]["text"]
        
        # Enviar a Telegram
        if len(ai_reply) > 4000:
            for i in range(0, len(ai_reply), 4000):
                bot.send_message(message.chat.id, ai_reply[i:i+4000])
        else:
            bot.reply_to(message, ai_reply, parse_mode="Markdown")
        
        # --- RESPALDO GITHUB ---
        try:
            branch_name = f"run-{message.message_id}"
            main_sha = repo.get_branch("main").commit.sha
            repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main_sha)
            repo.create_file(
                path=f"modelos/analisis_{message.message_id}.md",
                message="Quant AI Update",
                content=ai_reply,
                branch=branch_name
            )
            pr = repo.create_pull(
                title=f"Analisis {message.message_id}",
                body="QuantBet AI Analysis",
                head=branch_name,
                base="main"
            )
            bot.send_message(message.chat.id, f"✅ Guardado: {pr.html_url}", disable_web_page_preview=True)
        except:
            pass

    except Exception as e:
        bot.reply_to(message, f"⚠️ Error Crítico: {str(e)}")

bot.infinity_polling()
