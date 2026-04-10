import telebot
import requests
import os
import base64
from github import Github, Auth

bot = telebot.TeleBot(os.getenv("TELEGRAM_BOT_TOKEN"))
xai_api_key = os.getenv("XAI_API_KEY")

# Nueva forma recomendada de autenticación GitHub
GITHUB_TOKEN = os.getenv("TOKEN_GITHUB")
if not GITHUB_TOKEN:
    print("Error: TOKEN_GITHUB no encontrado")
    exit(1)

auth = Auth.Token(GITHUB_TOKEN)
gh = Github(auth=auth)
repo = gh.get_repo("josebernardinogonza-pixel/telegram-ai-bot-pro")  # ← CAMBIA "TU_USUARIO" por tu usuario real de GitHub

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "¡Hola! Soy tu bot IA profesional 🚀\nEnvíame instrucción + imagen/video/archivo y genero todo en GitHub.")

@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_message(message):
    prompt = message.text or "Analiza este archivo y genera un resultado profesional."
    bot.reply_to(message, "Procesando con Grok... ⏳")
    
    # Descargar archivo si hay
    file_info = None
    if message.photo:
        file_info = bot.get_file(message.photo[-1].file_id)
    elif message.video:
        file_info = bot.get_file(message.video.file_id)
    elif message.document:
        file_info = bot.get_file(message.document.file_id)
    
    files = []
    if file_info:
        downloaded = bot.download_file(file_info.file_path)
        base64_file = base64.b64encode(downloaded).decode('utf-8')
        mime = "image" if message.photo else "video" if message.video else "application"
        files = [{"type": "image_url" if message.photo else "video_url" if message.video else "file", 
                  "image_url" if message.photo else "video_url" if message.video else "url": f"data:{mime}/octet-stream;base64,{base64_file}"}]
    
    # Llamada a Grok (ajusta según el modelo actual)
    headers = {"Authorization": f"Bearer {xai_api_key}", "Content-Type": "application/json"}
    data = {
        "model": "grok-beta",   # o el modelo con visión que esté disponible
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}] + files}],
        "max_tokens": 4096
    }
    
    try:
        response = requests.post("https://api.x.ai/v1/chat/completions", json=data, headers=headers)
        ai_reply = response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        ai_reply = f"Error al llamar a Grok: {str(e)}"
    
    bot.reply_to(message, ai_reply[:4000])  # Telegram tiene límite de mensaje
    
    # Crear rama y PR en GitHub
    try:
        branch = f"ai-bot-{message.message_id}"
        repo.create_git_ref(ref=f"refs/heads/{branch}", sha=repo.get_git_ref("heads/main").object.sha)
        repo.create_file(f"generations/{message.message_id}/resultado.md", 
                         f"Generado por Telegram AI Bot - {prompt[:80]}", 
                         ai_reply, branch=branch)
        pr = repo.create_pull(title=f"🤖 AI Generation #{message.message_id}", 
                              body=ai_reply[:2000], 
                              head=branch, base="main")
        bot.reply_to(message, f"✅ Listo!\nPull Request creado: {pr.html_url}")
    except Exception as e:
        bot.reply_to(message, f"Error al crear PR en GitHub: {str(e)}")

print("Bot iniciado...")
bot.polling(none_stop=True)
