import telebot
import requests
import os
import base64
import uuid
import time
from github import Github, Auth

# Configuración
bot = telebot.TeleBot(os.getenv("TELEGRAM_BOT_TOKEN"))
xai_api_key = os.getenv("XAI_API_KEY")
GITHUB_TOKEN = os.getenv("TOKEN_GITHUB")

if not GITHUB_TOKEN or not xai_api_key:
    print("Error: Faltan variables de entorno")
    exit(1)

# Autenticación GitHub
auth = Auth.Token(GITHUB_TOKEN)
gh = Github(auth=auth)
repo = gh.get_repo("josebernardinogonza-pixel/telegram-ai-bot-pro")

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "¡Hola! Soy tu Asistente IA Profesional con Grok 4.20 Reasoning + Grok Imagine 🚀\n\n"
                          "• Texto normal → Grok Reasoning (/v1/responses)\n"
                          "• 'Genera imagen de ...' → Imagen con Grok Imagine\n"
                          "• 'Genera video de ...' → Video con Grok Imagine Video\n"
                          "• Adjunta foto → La analiza y responde\n"
                          "Todo se guarda en GitHub con PR.")

def is_image_request(prompt):
    keywords = ["genera imagen", "crea imagen", "dibuja", "ilustra", "image of", "generate image"]
    return any(kw.lower() in prompt.lower() for kw in keywords)

def is_video_request(prompt):
    keywords = ["genera video", "crea video", "haz un video", "video de", "genera un clip", "create video"]
    return any(kw.lower() in prompt.lower() for kw in keywords)

@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_message(message):
    prompt = message.text or "Analiza este archivo y genera un resultado profesional."
    bot.reply_to(message, "Procesando con Grok 4.20 Reasoning... ⏳")

    # Preparar input para /v1/responses (puede incluir imágenes como base64)
    input_content = [{"role": "user", "content": prompt}]

    attached_image_data = None
    if message.photo:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        attached_image_data = downloaded
        # Para visión: se puede enviar como parte del content, pero /v1/responses lo maneja diferente
        bot.reply_to(message, "📸 Imagen detectada, la enviaré junto al prompt.")

    # === GENERACIÓN DE VIDEO ===
    if is_video_request(prompt):
        bot.reply_to(message, "🎥 Generando video con Grok Imagine Video... (puede tardar 30-90s)")
        try:
            headers = {"Authorization": f"Bearer {xai_api_key}", "Content-Type": "application/json"}
            data = {
                "model": "grok-imagine-video",
                "prompt": prompt,
                "duration": 8,
                "aspect_ratio": "16:9",
                "resolution": "720p"
            }
            if attached_image_data:
                data["image"] = "data:image/png;base64," + base64.b64encode(attached_image_data).decode('utf-8')

            resp = requests.post("https://api.x.ai/v1/videos/generations", json=data, headers=headers)
            resp_json = resp.json()

            if "data" in resp_json and resp_json["data"]:
                video_url = resp_json["data"][0].get("url")
                if video_url:
                    video_data = requests.get(video_url).content
                    video_filename = f"video_{uuid.uuid4().hex[:8]}.mp4"
                    ai_reply = f"🎥 **Video generado exitosamente**\nPrompt: {prompt}\n\nURL temporal: {video_url}"
                else:
                    ai_reply = "❌ No se recibió URL de video."
                    video_data = None
                    video_filename = None
            else:
                ai_reply = f"❌ Error en video: {resp_json.get('error', resp_json)}"
                video_data = None
                video_filename = None
        except Exception as e:
            ai_reply = f"❌ Error generando video: {str(e)}"
            video_data = None
            video_filename = None

    # === GENERACIÓN DE IMAGEN ===
    elif is_image_request(prompt):
        bot.reply_to(message, "🎨 Generando imagen con Grok Imagine...")
        try:
            headers = {"Authorization": f"Bearer {xai_api_key}", "Content-Type": "application/json"}
            data = {
                "model": "grok-imagine-image",
                "prompt": prompt,
                "n": 1,
                "size": "1024x1024"
            }
            resp = requests.post("https://api.x.ai/v1/images/generations", json=data, headers=headers)
            resp_json = resp.json()

            if "data" in resp_json and resp_json["data"]:
                image_url = resp_json["data"][0].get("url")
                img_data = requests.get(image_url).content if image_url else None
                image_filename = f"image_{uuid.uuid4().hex[:8]}.png"
                ai_reply = f"🎨 **Imagen generada con Grok Imagine**\nPrompt: {prompt}\n\n{image_url or ''}"
            else:
                ai_reply = f"❌ Error en imagen: {resp_json.get('error', resp_json)}"
                img_data = None
                image_filename = None
        except Exception as e:
            ai_reply = f"❌ Error generando imagen: {str(e)}"
            img_data = None
            image_filename = None
        video_data = None
        video_filename = None

    # === MODO CHAT NORMAL CON /v1/responses ===
    else:
        headers = {"Authorization": f"Bearer {xai_api_key}", "Content-Type": "application/json"}
        data = {
            "model": "grok-4.20-reasoning",   # ← El modelo de tu curl
            "input": input_content
        }
        try:
            resp = requests.post("https://api.x.ai/v1/responses", json=data, headers=headers)
            resp_json = resp.json()

            if "output" in resp_json:
                ai_reply = resp_json["output"]  # formato típico de /v1/responses
            elif "content" in resp_json:
                ai_reply = resp_json["content"]
            else:
                ai_reply = f"Respuesta recibida: {str(resp_json)[:1000]}"
        except Exception as e:
            ai_reply = f"❌ Error con /v1/responses: {str(e)}"
        video_data = None
        video_filename = None
        img_data = None
        image_filename = None

    # Responder en Telegram
    bot.reply_to(message, ai_reply[:3800] + ("..." if len(ai_reply) > 3800 else ""))

    # Crear PR en GitHub
    try:
        branch_name = f"ai-generation-{message.message_id}"
        main_ref = repo.get_git_ref("heads/main")
        repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main_ref.object.sha)

        # Guardar resultado texto
        repo.create_file(
            path=f"generations/{message.message_id}/resultado.md",
            message=f"🤖 Generado por Bot - {prompt[:80]}",
            content=ai_reply,
            branch=branch_name
        )

        # Guardar imagen si existe
        if 'img_data' in locals() and img_data and 'image_filename' in locals():
            repo.create_file(
                path=f"generations/{message.message_id}/{image_filename}",
                message="🎨 Imagen generada",
                content=img_data,
                branch=branch_name
            )

        # Guardar video si existe
        if 'video_data' in locals() and video_data and 'video_filename' in locals():
            repo.create_file(
                path=f"generations/{message.message_id}/{video_filename}",
                message="🎥 Video generado",
                content=video_data,
                branch=branch_name
            )

        pr = repo.create_pull(
            title=f"🤖 AI Bot #{message.message_id}",
            body=f"**Prompt:** {prompt}\n\n**Respuesta:**\n{ai_reply[:1500]}...",
            head=branch_name,
            base="main"
        )
        bot.reply_to(message, f"✅ ¡Listo!\nPR creado: {pr.html_url}")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Error al crear PR: {str(e)}")

print("✅ Bot iniciado con /v1/responses + Grok Imagine (imagen y video)")
bot.polling(none_stop=True)
