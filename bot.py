import telebot
import requests
import os
import json
import base64
from github import Github, Auth

# ---------------- CREDENCIALES ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("TOKEN_GITHUB")

# ⚠️ NOMBRE EXACTO DEL MODELO DE GOOGLE
GEMINI_MODEL = "gemini-1.5-flash-latest"

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# AUTENTICACIÓN EN GITHUB
auth = Auth.Token(GITHUB_TOKEN)
gh = Github(auth=auth)
repo = gh.get_repo("josebernardinogonza-pixel/telegram-ai-bot-pro")  # Tu repo

# SYSTEM PROMPT: MODELO CUANTITATIVO AVANZADO
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
        "📐 **Iniciando Sistema QuantBet AI (Powered by Gemini)** 📊\n\n"
        "Modelo cuantitativo en línea. Procesando métricas avanzadas (xG, Poisson, +EV) y correlaciones.\n\n"
        "Ingresa el partido o mercado que deseas modelar hoy:"
    )
    bot.reply_to(message, welcome_msg, parse_mode="Markdown")

@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_message(message):
    bot.send_chat_action(message.chat.id, 'typing')
    
    user_prompt = message.text or message.caption or "Ejecuta un modelo predictivo para la jornada de hoy."
    
    # Construir la estructura de partes para Gemini
    parts = [{"text": user_prompt}]

    # Si el usuario envía una imagen, la procesamos para Gemini Vision
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

    # URL oficial de Gemini API con la variable del modelo
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # Payload exacto que pide Google
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
            "topP": 0.9
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        result = response.json()
        
        # Manejo de errores de Gemini
        if "error" in result:
            error_msg = result["error"].get("message", "Error desconocido")
            bot.reply_to(message, f"⚠️ Error de la API de Gemini: {error_msg}")
            return
            
        # Extraer la respuesta de Gemini
        try:
            ai_reply = result["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            bot.reply_to(message, f"⚠️ Gemini devolvió una estructura inesperada:\n{json.dumps(result)[:1000]}")
            return
        
        # Dividir el mensaje si supera el límite de Telegram (4000 caracteres)
        max_length = 4000
        if len(ai_reply) > max_length:
            for i in range(0, len(ai_reply), max_length):
                bot.reply_to(message, ai_reply[i:i+max_length])
        else:
            bot.reply_to(message, ai_reply)
        
        # Guardar en GitHub
        branch = f"quant-model-{message.message_id}"
        repo.create_git_ref(ref=f"refs/heads/{branch}", sha=repo.get_git_ref("heads/main").object.sha)
        repo.create_file(
            f"modelos/{message.message_id}/analisis_quant.md", 
            f"Modelo Quant - {user_prompt[:30]}", 
            ai_reply, 
            branch=branch
        )
        pr = repo.create_pull(title=f"📐 Quant AI: {user_prompt[:40]}...", body=ai_reply, head=branch, base="main")
        bot.reply_to(message, f"✅ ¡Modelo ejecutado y guardado en GitHub!\nPR: {pr.html_url}")

    except Exception as e:
        bot.reply_to(message, f"⚠️ Error general: {str(e)}")

bot.infinity_polling()
