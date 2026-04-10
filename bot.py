import telebot
import requests
import os
import base64
from github import Github, Auth

# Configuración
bot = telebot.TeleBot(os.getenv("TELEGRAM_BOT_TOKEN"))
xai_api_key = os.getenv("XAI_API_KEY")
GITHUB_TOKEN = os.getenv("TOKEN_GITHUB")

if not GITHUB_TOKEN:
    print("Error: TOKEN_GITHUB no encontrado en las variables de entorno")
    exit(1)

# Autenticación moderna de GitHub (sin deprecation warning)
auth = Auth.Token(GITHUB_TOKEN)
gh = Github(auth=auth)
repo = gh.get_repo("josebernardinogonza-pixel/telegram-ai-bot-pro")  # ← Cambia si tu usuario es diferente

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "¡Hola! Soy tu Asistente IA Profesional 🚀\n"
                          "Envíame una instrucción + imagen/video/archivo y lo procesaré con Grok.\n"
                          "Todo se guardará automáticamente en GitHub.")

@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_message(message):
    prompt = message.text or "Analiza este archivo y genera un resultado profesional y detallado."
    bot.reply_to(message, "Procesando con Grok... ⏳")

    # Preparar contenido para Grok (texto + archivos)
    content = [{"type": "text", "text": prompt}]

    # Descargar y convertir archivo/imagen/video a base64
    file_info = None
    if message.photo:
        file_info = bot.get_file(message.photo[-1].file_id)
        media_type = "image"
    elif message.video:
        file_info = bot.get_file(message.video.file_id)
        media_type = "video"
    elif message.document:
        file_info = bot.get_file(message.document.file_id)
        media_type = "file"

    if file_info:
        try:
            downloaded = bot.download_file(file_info.file_path)
            base64_file = base64.b64encode(downloaded).decode('utf-8')
            content.append({
                "type": "image_url" if media_type == "image" else "file",
                "image_url" if media_type == "image" else "url": f"data:application/octet-stream;base64,{base64_file}"
            })
        except Exception as e:
            bot.reply_to(message, f"Error al procesar el archivo: {str(e)}")

    # Llamada a Grok API (modelo actualizado)
    headers = {
        "Authorization": f"Bearer {xai_api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "grok-4.20-0309-non-reasoning",   # Modelo rápido y estable en abril 2026
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 4096,
        "temperature": 0.7
    }

    try:
        response = requests.post("https://api.x.ai/v1/chat/completions", json=data, headers=headers)
        resp_json = response.json()

        if "choices" in resp_json and len(resp_json["choices"]) > 0:
            ai_reply = resp_json["choices"][0]["message"]["content"]
        elif "error" in resp_json:
            ai_reply = f"❌ Error de la API de xAI:\n{resp_json['error'].get('message', str(resp_json['error']))}"
        else:
            ai_reply = f"❌ Respuesta inesperada de Grok:\n{str(resp_json)[:800]}..."

    except Exception as e:
        ai_reply = f"❌ Error al conectar con Grok: {str(e)}"

    # Responder en Telegram (cortado si es muy largo)
    bot.reply_to(message, ai_reply[:3800] + ("..." if len(ai_reply) > 3800 else ""))

    # Crear rama + Pull Request en GitHub
    try:
        branch_name = f"ai-generation-{message.message_id}"
        main_ref = repo.get_git_ref("heads/main")
        repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main_ref.object.sha)

        # Guardar resultado
        file_path = f"generations/{message.message_id}/resultado.md"
        commit_message = f"🤖 Generado por Telegram Bot - {prompt[:80]}"

        repo.create_file(
            path=file_path,
            message=commit_message,
            content=ai_reply,
            branch=branch_name
        )

        pr = repo.create_pull(
            title=f"🤖 AI Bot: {prompt[:60]}...",
            body=f"**Instrucción:** {prompt}\n\n**Respuesta de Grok:**\n\n{ai_reply[:1500]}...",
            head=branch_name,
            base="main"
        )

        bot.reply_to(message, f"✅ ¡Listo!\nPull Request creado automáticamente:\n{pr.html_url}")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Se generó la respuesta pero hubo un error al crear el PR:\n{str(e)}")

print("✅ Bot iniciado correctamente...")
bot.polling(none_stop=True)
