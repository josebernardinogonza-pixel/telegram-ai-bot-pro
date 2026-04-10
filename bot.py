import telebot
import requests
import os
import base64
from github import Github  # para crear PR automático en GitHub

bot = telebot.TeleBot(os.getenv("TELEGRAM_BOT_TOKEN"))
xai_api_key = os.getenv("XAI_API_KEY")
gh = Github(os.getenv("TOKEN_GITHUB"))
repo = gh.get_repo("josebernardinogonza-pixel/telegram-ai-bot-pro")  # cambia por tu repo

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "¡Hola! Soy tu bot IA profesional 🚀\nEnvíame instrucción + imagen/video/archivo y genero todo en GitHub.")

@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_message(message):
    prompt = message.text or "Analiza este archivo y genera un resultado profesional."
    
    # Descargar archivo si hay (imagen, video, documento)
    file_info = None
    if message.photo:
        file_info = bot.get_file(message.photo[-1].file_id)
    elif message.video:
        file_info = bot.get_file(message.video.file_id)
    elif message.document:
        file_info = bot.get_file(message.document.file_id)
    
    files = None
    if file_info:
        downloaded = bot.download_file(file_info.file_path)
        # Convertir a base64 para Grok (visión)
        base64_file = base64.b64encode(downloaded).decode('utf-8')
        files = [{"type": "image_url" if message.photo else "video_url" if message.video else "file_url", "url": f"data:application/octet-stream;base64,{base64_file}"}]
    
    # Llamar a Grok API (visión + generación profesional)
    headers = {"Authorization": f"Bearer {xai_api_key}", "Content-Type": "application/json"}
    data = {
        "model": "grok-4",  # o el modelo actual con visión
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}] + (files or [])}],
        "max_tokens": 4096
    }
    # Si quieres generación de imagen/video con Grok Imagine, puedes agregar lógica aquí (fal.ai o direct xAI Imagine)
    
    response = requests.post("https://api.x.ai/v1/chat/completions", json=data, headers=headers)
    ai_reply = response.json()["choices"][0]["message"]["content"]
    
    # Responder en Telegram
    bot.reply_to(message, ai_reply)
    
    # Crear rama + PR en GitHub automáticamente
    branch = f"ai-generation-{message.message_id}"
    repo.create_git_ref(ref=f"refs/heads/{branch}", sha=repo.get_git_ref("heads/main").object.sha)
    # Aquí puedes crear archivos con el resultado (código, markdown, etc.)
    # Ejemplo simple: crear un archivo result.md
    repo.create_file(f"generations/{message.message_id}/resultado.md", f"Generado por bot Telegram - {prompt}", ai_reply, branch=branch)
    
    # Crear Pull Request
    pr = repo.create_pull(title=f"🤖 AI Bot: {prompt[:50]}", body=ai_reply, head=branch, base="main")
    bot.reply_to(message, f"✅ Resultado guardado en GitHub!\nPR listo: {pr.html_url}")

bot.polling()
