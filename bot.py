import telebot
import os
from github import Github, Auth
from google import genai
from google.genai import types

# ----------------- CREDENCIALES -----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("TOKEN_GITHUB")

# Usamos el modelo más reciente que soporta el nuevo SDK
GEMINI_MODEL_NAME = "gemini-2.0-flash" 

# Inicializar cliente de Google y Bot de Telegram
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
IMPORTANTE: Si usas símbolos matemáticos, asegúrate de que el formato sea limpio.
"""

@bot.message_handler(commands=['start'])
def start(message):
    welcome_msg = "📊 **QuantBet AI Online**. Tira el dato del partido o la foto de las cuotas y armamos el análisis."
    bot.reply_to(message, welcome_msg, parse_mode="Markdown")

@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_message(message):
    bot.send_chat_action(message.chat.id, 'typing')
    
    user_prompt = message.text or message.caption or "Analiza este evento deportivo."
    content_parts = [user_prompt]

    # Manejo de imágenes nativo con el nuevo SDK
    if message.photo:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_bytes = bot.download_file(file_info.file_path)
        content_parts.append(
            types.Part.from_bytes(data=downloaded_bytes, mime_type="image/jpeg")
        )

    try:
        # Llamada a Gemini
        response = client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=content_parts,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT
            )
        )
        ai_reply = response.text
        
        # --- ENVÍO A TELEGRAM CON PARCHE PARA EL ERROR 400 ---
        try:
            if len(ai_reply) > 4000:
                for i in range(0, len(ai_reply), 4000):
                    bot.send_message(message.chat.id, ai_reply[i:i+4000], parse_mode="Markdown")
            else:
                bot.reply_to(message, ai_reply, parse_mode="Markdown")
        except:
            # Si el Markdown de la IA viene roto, lo manda como texto plano para que no truene el bot
            if len(ai_reply) > 4000:
                for i in range(0, len(ai_reply), 4000):
                    bot.send_message(message.chat.id, ai_reply[i:i+4000])
            else:
                bot.reply_to(message, ai_reply)
        
        # --- RESPALDO EN GITHUB ---
        try:
            branch_name = f"analisis-{message.message_id}"
            main_sha = repo.get_branch("main").commit.sha
            repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main_sha)
            repo.create_file(
                path=f"modelos/analisis_{message.message_id}.md",
                message="QuantBet AI Update",
                content=ai_reply,
                branch=branch_name
            )
            repo.create_pull(
                title=f"Predicción {message.message_id}",
                body="Análisis generado por QuantBet AI",
                head=branch_name,
                base="main"
            )
        except Exception as ge:
            print(f"Error en GitHub: {ge}")

    except Exception as e:
        bot.reply_to(message, "⚠️ Hubo un bronca con la IA. Reintenta en un momento.")
        print(f"Error crítico: {e}")

if __name__ == "__main__":
    print("QuantBet AI jalando... ¡A cobrar esos verdes!")
    bot.infinity_polling()
