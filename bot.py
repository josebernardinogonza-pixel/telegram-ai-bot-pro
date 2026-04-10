import telebot
import requests
import os
import base64
from github import Github

# Credenciales
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
XAI_API_KEY = os.getenv("XAI_API_KEY")
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

Reglas: Usa Markdown. Ve directo al grano. Si el usuario sube una imagen, analízala con ojo de director de arte.
"""

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "👋 ¡Hola! Soy tu **Director Creativo AI** 🚀\n\nEnvíame una instrucción (y una imagen si quieres) y generaré contenido profesional, guardándolo automáticamente en GitHub.")

@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_message(message):
    bot.send_chat_action(message.chat.id, 'typing')
    
    # Obtener el texto o el pie de foto
    prompt = message.text or message.caption or "Analiza este archivo y genera un resultado profesional."
    
    messages_payload = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    # LÓGICA DINÁMICA: Elegir modelo y formato según si hay imagen o no
    if message.photo:
        # MODO VISIÓN (Nombre de modelo actualizado)
        model_to_use = "grok-2-vision-1212"
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        base64_image = base64.b64encode(downloaded).decode('utf-8')
        
        messages_payload.append({
            "role": "user", 
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        })
    else:
        # MODO TEXTO (Nombre de modelo actualizado)
        model_to_use = "grok-2-1212"
        messages_payload.append({
            "role": "user", 
            "content": prompt
        })

    # Llamar a Grok API
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": model_to_use,
        "messages": messages_payload,
        "temperature": 0.7,
        "top_p": 0.9
    }
    
    try:
        response = requests.post("https://api.x.ai/v1/chat/completions", json=data, headers=headers)
        response.raise_for_status() # Lanza error si la API falla
        
        ai_reply = response.json()["choices"][0]["message"]["content"]
        
        # Responder en Telegram
        bot.reply_to(message, ai_reply)
        
        # Crear rama + PR en GitHub automáticamente
        branch = f"ai-generation-{message.message_id}"
        repo.create_git_ref(ref=f"refs/heads/{branch}", sha=repo.get_git_ref("heads/main").object.sha)
        
        # Crear archivo Markdown con el resultado
        repo.create_file(
            f"generations/{message.message_id}/resultado.md", 
            f"Generado por bot Telegram - {prompt[:30]}", 
            ai_reply, 
            branch=branch
        )
        
        # Crear Pull Request
        pr = repo.create_pull(title=f"🤖 AI Bot: {prompt[:40]}...", body=ai_reply, head=branch, base="main")
        bot.reply_to(message, f"✅ ¡Resultado guardado en GitHub!\nPR listo: {pr.html_url}")

    except requests.exceptions.HTTPError as err:
        error_details = response.text if 'response' in locals() else str(err)
        bot.reply_to(message, f"⚠️ Error de la API de Grok: {error_details}")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Error general: {str(e)}")

# Usar infinity_polling para que no se caiga fácilmente
bot.infinity_polling()
