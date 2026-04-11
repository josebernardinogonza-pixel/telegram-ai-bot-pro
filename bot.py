import telebot
import requests
import os
from github import Github

# ---------------- CREDENCIALES ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FELO_API_KEY = os.getenv("FELO_API_KEY")
GITHUB_TOKEN = os.getenv("TOKEN_GITHUB")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
gh = Github(GITHUB_TOKEN)
repo = gh.get_repo("josebernardinogonza-pixel/telegram-ai-bot-pro")  # Tu repo

# EL SYSTEM PROMPT PROFESIONAL
SYSTEM_PROMPT = """
Actúa como "CreativeDirector AI", un Director Creativo Senior y experto en marketing de contenidos, copywriting persuasivo, dirección de arte y producción audiovisual. Tu objetivo es entregar resultados de calidad de agencia. Tu tono es profesional, moderno, persuasivo y directo. No uses lenguaje robótico.

Directrices:
1. Copywriting: Usa frameworks (AIDA, PAS). Gancho en los primeros 3 segundos. Párrafos cortos. Termina con un CTA claro.
2. Prompts Visuales: Redacta prompts exactos en inglés para Midjourney/DALL-E. Especifica estilo, iluminación, cámara y calidad.
3. Guiones: Entrega en tabla [AUDIO] y [VISUAL]. Indica ritmo y música.

Reglas: Usa Markdown. Ve directo al grano.
"""

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "👋 ¡Hola! Soy tu **Director Creativo AI** (Powered by Felo) 🚀\n\nEnvíame una instrucción y generaré contenido profesional, guardándolo automáticamente en GitHub.")

@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_message(message):
    bot.send_chat_action(message.chat.id, 'typing')
    
    # Obtener el texto (si es foto/video, obtiene el pie de foto)
    user_prompt = message.text or message.caption or "Genera un resultado profesional."
    
    # Como Felo solo acepta un "query", unimos el System Prompt con la instrucción del usuario
    combined_query = f"{SYSTEM_PROMPT}\n\n--- INSTRUCCIÓN DEL USUARIO ---\n{user_prompt}"

    # Configuración exacta de la API de Felo
    url = "https://openapi.felo.ai/v2/chat"
    headers = {
        "Authorization": f"Bearer {FELO_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "query": combined_query
    }
    
    try:
        # Llamada a Felo
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status() # Lanza error si hay problema de conexión
        
        result = response.json()
        
        # Leer la respuesta según la estructura de Felo
        if result.get("status") == "ok":
            ai_reply = result["data"]["answer"]
        else:
            error_msg = result.get("message", "Error desconocido en el servidor de Felo")
            bot.reply_to(message, f"⚠️ Felo rechazó la petición: {error_msg}")
            return
        
        # Responder en Telegram
        bot.reply_to(message, ai_reply)
        
        # Crear rama + PR en GitHub automáticamente
        branch = f"ai-generation-{message.message_id}"
        repo.create_git_ref(ref=f"refs/heads/{branch}", sha=repo.get_git_ref("heads/main").object.sha)
        
        # Crear archivo Markdown con el resultado
        repo.create_file(
            f"generations/{message.message_id}/resultado.md", 
            f"Generado por bot Telegram - {user_prompt[:30]}", 
            ai_reply, 
            branch=branch
        )
        
        # Crear Pull Request
        pr = repo.create_pull(title=f"🤖 AI Bot: {user_prompt[:40]}...", body=ai_reply, head=branch, base="main")
        bot.reply_to(message, f"✅ ¡Resultado guardado en GitHub!\nPR listo: {pr.html_url}")

    except requests.exceptions.HTTPError as err:
        error_details = response.text if 'response' in locals() else str(err)
        bot.reply_to(message, f"⚠️ Error HTTP de Felo: {error_details}")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Error general: {str(e)}")

# Usar infinity_polling para que no se caiga fácilmente
bot.infinity_polling()
