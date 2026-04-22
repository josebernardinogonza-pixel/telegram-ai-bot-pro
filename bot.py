import telebot
import os
import base64
import google.generativeai as genai
from github import Github, Auth

# ----------------- CREDENCIALES y CONFIGURACIÓN -----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("TOKEN_GITHUB")

# Vamos a calarle con la versión Pro a ver si esta sí la topa tu API Key
GEMINI_MODEL_NAME = "gemini-1.5-pro"

# Configurar la API Key
genai.configure(api_key=GEMINI_API_KEY)

# 🕵️ CHIVATO: Esto va a imprimir los modelos que SÍ tienes disponibles
print("👀 --- CHECANDO MODELOS PERMITIDOS PARA ESTA API KEY ---")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print(f"Error al listar modelos: {e}")
print("-------------------------------------------------------")

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

# Inicializar el modelo
try:
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL_NAME,
        system_instruction=SYSTEM_PROMPT
    )
except Exception as e:
    print(f"⚠️ Error al inicializar el modelo: {e}")

@bot.message_handler(commands=['start'])
def start(message):
    welcome_msg = "📊 **QuantBet AI Online**. Envía un partido o imagen de cuotas para analizar."
    bot.reply_to(message, welcome_msg, parse_mode="Markdown")

@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_message(message):
    bot.send_chat_action(message.chat.id, 'typing')
    
    user_prompt = message.text or message.caption or "Realiza un análisis predictivo."
    content_parts = [user_prompt]

    # Manejo de imágenes (base64)
    if message.photo:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        base64_image = base64.b64encode(downloaded).decode('utf-8')
        content_parts.append({
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": base64_image
            }
        })

    try:
        # LLAMADA A GEMINI
        response = model.generate_content(content_parts)
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
    print("Iniciando QuantBet AI...")
    bot.infinity_polling()
