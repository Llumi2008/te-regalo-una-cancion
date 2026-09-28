import os
import re
import subprocess
from dotenv import load_dotenv
import telebot
from telebot import types

# Cargar variables secretas desde .env
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID:
    raise ValueError("Faltan variables en el archivo .env")

bot = telebot.TeleBot(TOKEN)

# Memoria temporal para guardar la versión elegida por el usuario
user_data = {}

def es_autorizado(message_or_call):
    """Verifica que la interacción provenga únicamente de tu ID de Telegram."""
    chat_id = message_or_call.chat.id if hasattr(message_or_call, 'chat') else message_or_call.message.chat.id
    return str(chat_id) == str(CHAT_ID)

def obtener_ultima_version():
    """Lee el último tag registrado en Git localmente."""
    try:
        resultado = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True, text=True, check=True
        )
        tag = resultado.stdout.strip()
        return tag if tag else "v1.0.0"
    except Exception:
        return "v1.0.0"

def calcular_siguiente_version(version_actual, tipo):
    """Calcula automáticamente el número de la siguiente versión según SemVer."""
    tiene_v = version_actual.startswith('v')
    v_clean = version_actual[1:] if tiene_v else version_actual
    
    partes = [int(n) for n in re.findall(r'\d+', v_clean)]
    while len(partes) < 3:
        partes.append(0)
        
    x, y, z = partes[0], partes[1], partes[2]

    if tipo == 'patch':
        z += 1
    elif tipo == 'minor':
        y += 1
        z = 0
    elif tipo == 'major':
        x += 1
        y = 0
        z = 0

    nueva = f"{x}.{y}.{z}"
    return f"v{nueva}" if tiene_v else f"v{nueva}"

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if not es_autorizado(message):
        return
    bot.reply_to(
        message, 
        "👋 ¡Hola! Envíame el nuevo archivo PDF del cancionero para iniciar la actualización automática."
    )

@bot.message_handler(content_types=['document'])
def handle_pdf(message):
    if not es_autorizado(message):
        return

    if not message.document.file_name.lower().endswith('.pdf'):
        bot.reply_to(message, "⚠️ El archivo enviado debe ser formato .pdf")
        return

    try:
        # Descargar el PDF enviado
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        os.makedirs("pdf", exist_ok=True)
        pdf_path = os.path.join("pdf", "te doy una cancion.pdf")

        with open(pdf_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        # Consultar la última versión y calcular las siguientes
        version_actual = obtener_ultima_version()
        v_patch = calcular_siguiente_version(version_actual, 'patch')
        v_minor = calcular_siguiente_version(version_actual, 'minor')
        v_major = calcular_siguiente_version(version_actual, 'major')

        # Crear teclado interactivo con las opciones calculadas
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_patch = types.InlineKeyboardButton(f"🔧 Corrección menor/acordes ({v_patch})", callback_data=f"ver:{v_patch}")
        btn_minor = types.InlineKeyboardButton(f"🎶 Nuevas canciones / cambios ({v_minor})", callback_data=f"ver:{v_minor}")
        btn_major = types.InlineKeyboardButton(f"🚀 Edición o cambio mayor ({v_major})", callback_data=f"ver:{v_major}")
        markup.add(btn_patch, btn_minor, btn_major)

        bot.reply_to(
            message,
            f"📄 **PDF guardado correctamente.**\n\n"
            f"📌 Última versión registrada: **{version_actual}**\n\n"
            f"¿Qué tipo de actualización es esta?",
            reply_markup=markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        bot.reply_to(message, f"❌ Error al procesar el PDF: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('ver:'))
def callback_version(call):
    if not es_autorizado(call):
        return

    nueva_version = call.data.split(':')[1]
    user_data[call.message.chat.id] = {'version': nueva_version}

    bot.answer_callback_query(call.id)
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ Seleccionaste la versión **{nueva_version}**.\n\n"
             f"Ahora escribe un breve mensaje detallando los cambios realizados:",
        parse_mode="Markdown"
    )
    
    bot.register_next_step_handler(call.message, procesar_descripcion_y_publicar)

def procesar_descripcion_y_publicar(message):
    if not es_autorizado(message):
        return

    chat_id = message.chat.id
    datos = user_data.get(chat_id, {})
    tag_version = datos.get('version', 'v1.1.0')
    descripcion = message.text.strip()

    bot.send_message(chat_id, f"⏳ Publicando versión **{tag_version}** en GitHub...")

    try:
        # Ejecutar los comandos de Git
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", f"Actualización {tag_version}: {descripcion}"], check=True)
        subprocess.run(["git", "tag", "-a", tag_version, "-m", descripcion], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        subprocess.run(["git", "push", "origin", tag_version], check=True)

        # Plantilla de mensaje para WhatsApp
        mensaje_whatsapp = (
            f"🎶 *CANCIONERO DEL CORO ACTUALIZADO* 🎶\n\n"
            f"📌 *Versión:* {tag_version}\n"
            f"📝 *Novedades:* {descripcion}\n\n"
            f"📖 *Consulta o descarga el cancionero en línea aquí:*\n"
            f"https://llumi2008.github.io/te-regalo-una-cancion/\n\n"
            f"¡Dios les bendiga!"
        )

        bot.send_message(
            chat_id, 
            f"🎉 **¡Versión {tag_version} publicada con éxito en GitHub!**\n\n"
            f"📋 **Mensaje listo para copiar y pegar en WhatsApp:**\n\n"
            f"```\n{mensaje_whatsapp}\n```",
            parse_mode="Markdown"
        )

    except subprocess.CalledProcessError as e:
        bot.send_message(
            chat_id, 
            f"❌ **Error de Git:**\n`{str(e)}`"
        )

print("🤖 Bot interactivo en ejecución... Presiona Ctrl+C para detenerlo.")
bot.infinity_polling()
