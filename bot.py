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

# ✅ CAMBIO CLAVE: Usamos el nombre base del modelo para evitar errores de ruta en v1beta
GEMINI_MODEL = "gemini-1.5-flash" 

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# AUTENTICACIÓN EN GITHUB
auth = Auth.Token(GITHUB_TOKEN)
gh = Github(auth=auth)
repo = gh.get_repo("josebernardinogonza-pixel/telegram-ai-bot-pro")

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
    
    # Partes para el prompt (Soporta texto e imágenes)
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

    # URL actualizada
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    headers = {"Content-Type": "application/json"}
    
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
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        result = response.json()
        
        if "error" in result:
            error_msg = result["error"].get("message", "Error desconocido")
            bot.reply_to(message, f"⚠️ Error de la API de Gemini: {error_msg}")
            return
            
        try:
            ai_reply = result["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            bot.reply_to(message, "⚠️ No se pudo procesar la respuesta del modelo.")
            return
        
        # Envío de respuesta con manejo de longitud
        if len(ai_reply) > 4000:
            for i in range(0, len(ai_reply), 4000):
                bot.send_message(message.chat.id, ai_reply[i:i+4000])
        else:
            bot.reply_to(message, ai_reply)
        
        # --- Lógica de GitHub ---
        try:
            branch_name = f"quant-{message.message_id}"
            main_ref = repo.get_git_ref("heads/main")
            repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main_ref.object.sha)
            
            repo.create_file(
                path=f"modelos/analisis_{message.message_id}.md",
                message=f"Quant AI: {user_prompt[:30]}",
                content=ai_reply,
                branch=branch_name
            )
            
            pr = repo.create_pull(
                title=f"📐 Analisis: {user_prompt[:40]}",
                body=f"Análisis generado por QuantBet AI.\nPrompt original: {user_prompt}",
                head=branch_name,
                base="main"
            )
            bot.send_message(message.chat.id, f"✅ Respaldo creado en GitHub:\n{pr.html_url}")
        except Exception as git_err:
            print(f"Error GitHub: {git_err}") # No interrumpimos al usuario si GitHub falla

    except Exception as e:
        bot.reply_to(message, f"⚠️ Error general: {str(e)}")

bot.infinity_polling()
