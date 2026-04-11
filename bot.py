import telebot
import requests
import os
import json
from github import Github, Auth

# ---------------- CREDENCIALES ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FELO_API_KEY = os.getenv("FELO_API_KEY")
GITHUB_TOKEN = os.getenv("TOKEN_GITHUB")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# AUTENTICACIÓN EN GITHUB
auth = Auth.Token(GITHUB_TOKEN)
gh = Github(auth=auth)
repo = gh.get_repo("josebernardinogonza-pixel/telegram-ai-bot-pro")  # Tu repo

# NUEVO SYSTEM PROMPT: MODELO CUANTITATIVO AVANZADO
SYSTEM_PROMPT = """
Actúa como "QuantBet AI", un modelo de análisis cuantitativo deportivo de alto nivel. Tu objetivo es identificar ineficiencias en las cuotas y generar pronósticos (+EV) basados en matemáticas avanzadas.

Directrices de Análisis para Modelado de Parlays:
1. Prioridad de Datos: Basa tu análisis en datos recientes, alineaciones, lesiones y contexto táctico real. Ignora narrativas de prensa.
2. Filtrado por Valor Esperado (+EV): El objetivo no es predecir ganadores, sino identificar ineficiencias. Selecciona opciones donde tu probabilidad calculada (P_modelo) sea mayor a la Probabilidad Implícita (IP) de la cuota.
3. Probabilidad Condicional: Para eventos correlacionados (Same Game Parlay), aplica lógica de correlación (simulación de Monte Carlo conceptual).
4. Métricas Predictivas: Descarta estadísticas de superficie. Basa la proyección en xG (Goles Esperados), xGA, y conceptos de Distribución de Poisson para calcular probabilidades exactas.
5. Optimización Probabilística: Evalúa el riesgo usando conceptos de calibración de probabilidades (Log-Loss).
6. Gestión de Capital: Sugiere el 'Stake' utilizando una Fracción de Kelly (1/4 o 1/8) para proteger el bankroll.

Formato de Salida:
- Presenta el análisis de forma estructurada, profesional y altamente técnica.
- Usa Markdown (negritas, listas) y emojis sobrios (📊, 📐, 💰, 📉).
- Muestra siempre la justificación matemática/estadística (xG, +EV) detrás de cada selección.
"""

@bot.message_handler(commands=['start'])
def start(message):
    welcome_msg = (
        "📐 **Iniciando Sistema QuantBet AI** 📊\n\n"
        "Modelo cuantitativo en línea. Procesando métricas avanzadas (xG, Poisson, +EV) y correlaciones de Monte Carlo.\n\n"
        "Ingresa el partido o mercado que deseas modelar hoy:"
    )
    bot.reply_to(message, welcome_msg, parse_mode="Markdown")

@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_message(message):
    bot.send_chat_action(message.chat.id, 'typing')
    
    user_prompt = message.text or message.caption or "Ejecuta un modelo predictivo para la jornada de hoy."
    combined_query = f"{SYSTEM_PROMPT}\n\nInstrucción del usuario:\n{user_prompt}"

    url = "https://openapi.felo.ai/v2/chat"
    headers = {
        "Authorization": f"Bearer {FELO_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "query": combined_query
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        
        try:
            result = response.json()
        except ValueError:
            bot.reply_to(message, f"⚠️ Error de conexión. Devolvió esto:\n{response.text[:1000]}")
            return
        
        if result.get("status") == 200 or result.get("code") == "OK":
            ai_reply = result["data"]["answer"]
        else:
            debug_info = json.dumps(result, indent=2)
            bot.reply_to(message, f"⚠️ Error del servidor:\n{debug_info[:3000]}")
            return
        
        # Dividir el mensaje si supera el límite de Telegram
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
