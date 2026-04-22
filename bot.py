import telebot
import os
import base64
import google.generativeai as genai  # <-- 1. SOLUCIÓN: Esta importación crucial que me mostraste
from github import Github, Auth

# ----------------- CREDENCIALES y CONFIGURACIÓN -----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("TOKEN_GITHUB")
GEMINI_MODEL_NAME = "gemini-1.5-flash"

# ✅ 2. Configurar la API Key (como en tu imagen)
genai.configure(api_key=GEMINI_API_KEY)

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

# ✅ 3. Inicializar el modelo con el System Instruction (Método limpio y oficial)
model = genai.GenerativeModel(
    model_name=GEMINI_MODEL_NAME,
    system_instruction=SYSTEM_PROMPT
)

@bot.message_handler(commands=['start'])
def start(message):
    welcome_msg = "📊 **QuantBet AI Online**. Envía un partido o imagen de cuotas para analizar."
    bot.reply_to(message, welcome_msg, parse_mode="Markdown")

@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_message(message):
    bot.send_chat_action(message.chat.id, 'typing')
    
    user_prompt = message.text or message.caption or "Realiza un análisis predictivo."
    # Preparamos las partes del mensaje para Gemini
    content_parts = [user_prompt]

    # Manejo de imágenes (base64)
    if message.photo:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        base64_image = base64.b64encode(downloaded).decode('utf-8')
        # Formato correcto de imagen para la librería oficial
        content_parts.append({
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": base64_image
            }
        })

    try:
        # ✅ 4. LLAMADA A GEMINI (Método oficial, mucho más limpio que usar REST)
        # Como hemos inicializado el modelo con 'system_instruction', Gemini ya lo sabe.
        response = model.generate_content(content_parts)
        
        # ✅ 5. Acceder a la respuesta (como en tu imagen)
        ai_reply = response.text
        
        # Enviar respuesta a Telegram (Manejo de mensajes largos)
        if len(ai_reply) > 4000:
            for i in range(0, len(ai_reply), 4000):
                bot.send_message(message.chat.id, ai_reply[i:i+4000])
        else:
            bot.reply_to(message, ai_reply, parse_mode="Markdown")
        
        # --- RESPALDO GITHUB (Inalterado, con mejores mensajes de error) ---
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
            # Imprimir el error en la consola de GitHub Actions para depurar, sin afectar la experiencia del usuario en Telegram
            print(f"Error al guardar en GitHub: {git_error}")

    except Exception as e:
        bot.reply_to(message, f"⚠️ Error Crítico en Gemini: {str(e)}")

# Bloque principal para ejecutar el bot
if __name__ == "__main__":
    print("Iniciando QuantBet AI con la librería oficial, como debe ser...")
    bot.infinity_polling()
