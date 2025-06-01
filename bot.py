import discord
import asyncio
from discord.ext import commands
import os
from dotenv import load_dotenv
import textwrap
import tempfile
from gtts import gTTS
import threading
import logging
import websocket
import json
import re

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Configuración
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
TIKTOK_USERNAME = os.getenv('TIKTOK_USERNAME') or 'juanjo_llovera'

# Crear el bot de Discord con intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Variables globales
voice_client = None
is_monitoring = False
monitor_thread = None
processed_comments = set()
text_channel = None  # Almacenar el canal de texto donde se ejecuta !iniciar

def clean_text(text):
    """Elimina emojis, nombres, caracteres no deseados y filtra idiomas no latinos"""
    try:
        comment = text.split("dijo: ")[1].strip()
    except IndexError:
        comment = text

    latin_pattern = re.compile(
        r'^[\w\s.,!?¿¡áéíóúñÁÉÍÓÚÑ\'"-]*$',
        flags=re.UNICODE
    )

    if not latin_pattern.match(comment):
        logger.info(f"Comentario descartado (contiene caracteres no latinos): {comment}")
        return ""

    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F700-\U0001F77F"
        u"\U0001F780-\U0001F7FF"
        u"\U0001F800-\U0001F8FF"
        u"\U0001F900-\U0001F9FF"
        u"\U0001FA00-\U0001FA6F"
        u"\U0001FA70-\U0001FAFF"
        u"\U00002700-\U000027BF"
        u"\U0001F1E0-\U0001F1FF"
        "]+",
        flags=re.UNICODE
    )

    cleaned_text = emoji_pattern.sub(r'', comment).strip()
    cleaned_text = re.sub(r'[^\w\s.,!?¿¡áéíóúñÁÉÍÓÚÑ\'"-]', '', cleaned_text)
    
    if not cleaned_text or re.match(r'^[\s.,!?¿¡\'"-]*$', cleaned_text):
        logger.info(f"Comentario descartado (vacío o solo puntuación después de limpiar): {comment}")
        return ""
    
    return cleaned_text

def on_message(ws, message):
    data = json.loads(message)
    comment = data['message']
    comment_id = str(hash(comment))
    
    if comment_id not in processed_comments:
        processed_comments.add(comment_id)
        if len(processed_comments) > 200:
            processed_comments.clear()
        
        cleaned_comment = clean_text(comment)
        if not cleaned_comment:
            return
        logger.info(f"Comentario limpio: {cleaned_comment}")
        asyncio.run_coroutine_threadsafe(text_to_speech(cleaned_comment), bot.loop)

def on_error(ws, error):
    logger.error(f"Error en WebSocket: {error}")

def on_close(ws, close_status_code, close_msg):
    logger.info("Conexión WebSocket cerrada")

def start_websocket():
    ws = websocket.WebSocketApp("ws://localhost:8080",
                               on_message=on_message,
                               on_error=on_error,
                               on_close=on_close)
    ws.run_forever()

ws_thread = threading.Thread(target=start_websocket)
ws_thread.daemon = True
ws_thread.start()

@bot.event
async def on_ready():
    logger.info(f'Bot conectado como {bot.user}')

@bot.command()
async def iniciar(ctx):
    """Inicia el monitoreo de TikTok Live y conecta al canal de voz"""
    global voice_client, is_monitoring, monitor_thread, text_channel
    
    if not ctx.author.voice:
        await ctx.send("¡Necesitas estar en un canal de voz primero!")
        return
    
    voice_channel = ctx.author.voice.channel
    if voice_client and voice_client.is_connected():
        await voice_client.move_to(voice_channel)
    else:
        voice_client = await voice_channel.connect()
    
    text_channel = ctx.channel
    
    await ctx.send(f"Conectado al canal de voz: {voice_channel.name}")
    await ctx.send(f"Monitoreando el directo de TikTok de @{TIKTOK_USERNAME} a través de WebSocket")
    
    is_monitoring = True
    if monitor_thread is None or not monitor_thread.is_alive():
        monitor_thread = threading.Thread(target=start_tiktok_monitoring)
        monitor_thread.daemon = True
        monitor_thread.start()

@bot.command()
async def detener(ctx):
    """Detiene el monitoreo y desconecta del canal de voz"""
    global voice_client, is_monitoring, text_channel
    
    is_monitoring = False
    text_channel = None
    
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        voice_client = None
    
    await ctx.send("Bot detenido y desconectado del canal de voz")

def start_tiktok_monitoring():
    """Inicia el monitoreo de TikTok Live a través de WebSocket"""
    logger.info(f"Monitoreo iniciado para @{TIKTOK_USERNAME}. Los comentarios se recibirán a través de WebSocket.")

async def text_to_speech(text):
    """Convierte texto a voz usando gTTS"""
    try:
        if not voice_client or not voice_client.is_connected():
            logger.warning("No hay conexión de voz para reproducir TTS")
            return
            
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
            temp_filename = temp_file.name
        
        tts = gTTS(text=text, lang='es')
        tts.save(temp_filename)
        
        while voice_client.is_playing():
            await asyncio.sleep(0.5)
            
        voice_client.play(discord.FFmpegPCMAudio(executable="ffmpeg", source=temp_filename), 
                        after=lambda e: cleanup_audio(e, temp_filename))
    except Exception as e:
        logger.error(f"Error en TTS: {str(e)}")

def cleanup_audio(error, filename):
    """Limpia el archivo de audio temporal después de reproducirlo"""
    if error:
        logger.error(f"Error al reproducir audio: {error}")
    
    try:
        os.remove(filename)
    except Exception as e:
        logger.error(f"Error al eliminar archivo temporal: {str(e)}")

@bot.command()
async def probar(ctx, *, mensaje="Mensaje de prueba"):
    """Prueba la funcionalidad de TTS con un mensaje personalizado"""
    if not ctx.author.voice:
        await ctx.send("¡Necesitas estar en un canal de voz para probar esto!")
        return
    
    global voice_client
    voice_channel = ctx.author.voice.channel
    
    if voice_client and voice_client.is_connected():
        if voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)
    else:
        voice_client = await voice_channel.connect()
    
    cleaned_mensaje = clean_text(mensaje)
    if not cleaned_mensaje:
        await ctx.send("El mensaje contiene caracteres no permitidos o está vacío después de limpiar.")
        return
    
    await text_to_speech(cleaned_mensaje)
    await ctx.send("Reproduciendo mensaje de prueba en el canal de voz")

@bot.command()
async def estado(ctx):
    """Muestra el estado actual del bot"""
    monitoring_status = "Activo" if is_monitoring else "Inactivo"
    voice_status = "Conectado" if voice_client and voice_client.is_connected() else "Desconectado"
    
    if voice_client and voice_client.is_connected():
        voice_channel = voice_client.channel.name
    else:
        voice_channel = "Ninguno"
    
    status_message = textwrap.dedent(f"""
    **Estado del Bot**
    - Monitoreo de TikTok: {monitoring_status}
    - Conexión de voz: {voice_status}
    - Canal de voz actual: {voice_channel}
    - Usuario de TikTok: @{TIKTOK_USERNAME}
    - Método: WebSocket (TikTok-Live-Connector)
    """)
    
    await ctx.send(status_message)

if __name__ == "__main__":
    try:
        logger.info("Iniciando el bot...")
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Error al iniciar el bot: {str(e)}")