import telebot
import requests
import os
import json
import base64
from github import Github, Auth

# ----------------- CREDENCIALES -----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("TOKEN_GITHUB")

# ✅ Usamos el modelo estándar y la versión v1 (Estable)
GEMINI_MODEL = "gemini-1.5-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ----------------- GITHUB SETUP -----------------
auth = Auth.Token(GITHUB_TOKEN)
gh = Github(auth=auth)
# Asegúrate de que este nombre de repo sea el correcto
repo_name = "josebernardinogonza-pixel/telegram-ai-bot-pro"
repo = gh.get_repo(repo_name)

# ----------------- SYSTEM PROMPT -----------------
SYSTEM_PROMPT = """
Actúa como "QuantBet AI", un modelo de análisis cuantitativo deportivo de alto nivel. Tu objetivo es identificar ineficiencias en las cuotas y generar pronósticos (+EV) basados en matemáticas avanzadas.

Directrices de Análisis para Modelado de Parlays:
1. Prioridad de Datos: Basa tu análisis en datos recientes, alineaciones y contexto táctico real.
2. Filtrado por Valor Esperado (+EV): Selecciona opciones donde tu probabilidad calculada (P_modelo) sea mayor a la Probabilidad Implícita (IP).
3. Probabilidad Condicional: Para eventos correlacionados, aplica lógica de correlación (simulación de Monte Carlo conceptual).
4. Métricas Predictivas: Basa la proyección en xG (Goles Esperados), xGA, y Distribución de Poisson.
5. Gestión de Capital: Sugiere el 'Stake' utilizando una Fracción de Kelly (1/4 o 1/8).

Formato de Salida:
- Presenta el análisis estructurado, profesional y técnico.
- Usa Markdown (negritas, listas) y emojis sobrios (📊, 📐, 💰, 📉).
- Muestra siempre la justificación matemática (+EV, xG) detrás de cada selección.
"""

@bot.message_handler(commands=['start'])
def start(message):
    welcome_msg = (
        "### 📐 Sistema QuantBet AI Activado 📊\n\n"
        "Modelo cuantitativo v1.5 operativo. Procesando métricas (xG, Poisson, +EV).\n\n"
        "Ingresa el partido o envía una captura de las cuotas para modelar:"
    )
    bot.reply_to(message, welcome_msg, parse_mode="Markdown")

@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_message(message):
    bot.send_chat_action(message.chat.id, 'typing')
    
    user_prompt = message.text or message.caption or "Analiza el mercado actual."
    
    # Preparar las partes del mensaje (Texto + Imagen si existe)
    parts = [{"text": user_prompt}]

    if message.photo:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        base64_image = base64.b64encode(downloaded).decode('utf-8')
        
        parts.append({
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": base64_image
            }
        })

    # Construcción del Payload para la API v1
    payload = {
        "systemInstruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": [{
            "role": "user",
            "parts": parts
        }],
        "generationConfig": {
            "temperature": 0.7,
            "topP": 0.9,
            "maxOutputTokens": 2048
        }
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        # Llamada a la API
        response = requests.post(API_URL, headers=headers, json=payload)
        result = response.json()
        
        # Manejo de errores específicos de Google
        if "error" in result:
            error_code = result["error"].get("code", "Desconocido")
            error_msg = result["error"].get("message", "Sin mensaje")
            bot.reply_to(message, f"⚠️ **Error API Gemini ({error_code}):**\n{error_msg}")
            return
            
        # Extraer respuesta
        try:
            ai_reply = result["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            bot.reply_to(message, "⚠️ La IA no generó una respuesta válida. Intenta con otro prompt.")
            return
        
        # Enviar respuesta a Telegram (Manejo de mensajes largos)
        if len(ai_reply) > 4000:
            for i in range(0, len(ai_reply), 4000):
                bot.send_message(message.chat.id, ai_reply[i:i+4000], parse_mode="Markdown")
        else:
            bot.reply_to(message, ai_reply, parse_mode="Markdown")
        
        # --- RESPALDO EN GITHUB ---
        try:
            # Crear rama única basada en el ID del mensaje para evitar conflictos
            branch_name = f"model-run-{message.message_id}"
            main_branch = repo.get_branch("main")
            repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main_branch.commit.sha)
            
            # Crear archivo en la carpeta modelos
            file_path = f"modelos/analisis_{message.message_id}.md"
            repo.create_file(
                path=file_path,
                message=f"Quant AI Run: {message.message_id}",
                content=ai_reply,
                branch=branch_name
            )
            
            # Crear Pull Request
            pr = repo.create_pull(
                title=f"📐 Nuevo Análisis Quant: {message.message_id}",
                body=f"Análisis automático generado para el usuario.\nPrompt: {user_prompt[:100]}",
                head=branch_name,
                base="main"
            )
            bot.send_message(message.chat.id, f"📦 **Respaldo en GitHub:**\n{pr.html_url}", disable_web_page_preview=True)
            
        except Exception as git_e:
            print(f"Error en GitHub: {git_e}")
            # No enviamos mensaje de error al usuario para no saturar si falla GitHub

    except Exception as e:
        bot.reply_to(message, f"⚠️ **Error General:** {str(e)}")

# Iniciar el bot
print("🤖 QuantBet AI está en línea...")
bot.infinity_polling()
