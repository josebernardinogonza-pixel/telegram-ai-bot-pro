import telebot
import requests
import os
import json
from github import Github

# ---------------- CREDENCIALES ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FELO_API_KEY = os.getenv("FELO_API_KEY")
GITHUB_TOKEN = os.getenv("TOKEN_GITHUB")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
gh = Github(GITHUB_TOKEN)
repo = gh.get_repo("josebernardinogonza-pixel/telegram-ai-bot-pro")  # Tu repo

# SYSTEM PROMPT
SYSTEM_PROMPT = "Actúa como Director Creativo Senior. Crea copy persuasivo (AIDA), prompts visuales exactos o guiones. Sé profesional, directo y usa Markdown."

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "👋 ¡Hola! Soy tu **Director Creativo AI** (Felo) 🚀\n\nEnvíame una instrucción.")

@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_message(message):
    bot.send_chat_action(message.chat.id, 'typing')
    
    user_prompt = message.text or message.caption or "Genera un resultado profesional."
    combined_query = f"{SYSTEM_PROMPT}\n\nInstrucción:\n{user_prompt}"

    url = "https://openapi.felo.ai/v2/chat"
    headers = {
        "Authorization": f"Bearer {FELO_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "query": combined_query
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        
        try:
            result = response.json()
        except ValueError:
            bot.reply_to(message, f"⚠️ Felo no devolvió un JSON. Devolvió esto:\n{response.text[:1000]}")
            return
        
        if result.get("status") == "ok":
            ai_reply = result["data"]["answer"]
        else:
            debug_info = json.dumps(result, indent=2)
            bot.reply_to(message, f"⚠️ Error de Felo:\n{debug_info[:3000]}")
            return
        
        # ---------------------------------------------------------
        # SOLUCIÓN: Dividir el mensaje si supera el límite de Telegram
        # ---------------------------------------------------------
        max_length = 4000
        if len(ai_reply) > max_length:
            for i in range(0, len(ai_reply), max_length):
                bot.reply_to(message, ai_reply[i:i+max_length])
        else:
            bot.reply_to(message, ai_reply)
        
        # Guardar en GitHub
        branch = f"ai-generation-{message.message_id}"
        repo.create_git_ref(ref=f"refs/heads/{branch}", sha=repo.get_git_ref("heads/main").object.sha)
        repo.create_file(
            f"generations/{message.message_id}/resultado.md", 
            f"Generado por bot - {user_prompt[:30]}", 
            ai_reply, 
            branch=branch
        )
        pr = repo.create_pull(title=f"🤖 AI Bot: {user_prompt[:40]}...", body=ai_reply, head=branch, base="main")
        bot.reply_to(message, f"✅ ¡Guardado en GitHub!\nPR listo: {pr.html_url}")

    except Exception as e:
        bot.reply_to(message, f"⚠️ Error general: {str(e)}")

bot.infinity_polling()
