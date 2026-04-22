import telebot
import os
from github import Github, Auth
from google import genai
from google.genai import types

# ----------------- CREDENCIALES y CONFIGURACIÓN -----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("TOKEN_GITHUB")

# Usamos la versión más reciente y perrona
GEMINI_MODEL_NAME = "gemini-2.5-flash"

# Inicializar el cliente (¡Esta es la forma nuevecita de Google!)
client = genai.Client(api_key=GEMINI_API_KEY)

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
    content_parts = [user_prompt]

    # Manejo de imágenes (Nueva forma nativa, más al tiro y sin usar base64)
    if message.photo:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_bytes = bot.download_file(file_info.file_path)
        # Añadimos la imagen directo en bytes
        content_parts.append(
            types.Part.from_bytes(data=downloaded_bytes, mime_type="image/jpeg")
        )

    try:
        # LLAMADA A GEMINI CON EL NUEVO SDK
        response = client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=content_parts,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT
            )
        )
        ai_reply = response.text
        
        # Enviar respuesta a Telegram
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
                title=f"Análisis {message.message_id}",
                body="QuantBet AI Analysis",
                head=branch_name,
                base="main"
            )
            bot.send_message(message.chat.id, f"✅ Guardado: {pr.html_url}", disable_web_page_preview=True)
        except Exception as git_error:
            print(f"Error al guardar en GitHub: {git_error}")

    except Exception as e:
        bot.reply_to(message, f"⚠️ Error Crítico en Gemini: {str(e)}")

# Bloque principal
if __name__ == "__main__":
    print("Iniciando QuantBet AI con el nuevo SDK de Google...")
    bot.infinity_polling()
