import os
import subprocess
from dotenv import load_dotenv
import telebot

# Cargar variables secretas desde .env
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID:
    raise ValueError("Faltan variables en el archivo .env")

bot = telebot.TeleBot(TOKEN)

def es_autorizado(message):
    """Verifica que el mensaje provenga únicamente de tu ID de Telegram."""
    return str(message.chat.id) == str(CHAT_ID)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if not es_autorizado(message):
        return
    bot.reply_to(
        message, 
        "👋 ¡Hola! Envíame el nuevo archivo PDF del cancionero para iniciar la actualización y publicación en GitHub."
    )

@bot.message_handler(content_types=['document'])
def handle_pdf(message):
    if not es_autorizado(message):
        return

    # Verificar que el archivo sea un PDF
    if not message.document.file_name.lower().endswith('.pdf'):
        bot.reply_to(message, "⚠️ El archivo enviado debe ser un formato .pdf")
        return

    try:
        # Descargar el PDF enviado
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # Crear carpeta pdf/ si no existe y guardar el archivo
        os.makedirs("pdf", exist_ok=True)
        pdf_path = os.path.join("pdf", "te doy una cancion.pdf")

        with open(pdf_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        msg = bot.reply_to(
            message, 
            "📄 **PDF guardado correctamente.**\n\n"
            "Por favor, responde a este mensaje indicando la **versión** y los **cambios** con este formato:\n\n"
            "`v1.1.0 - Añadido Salmo 23 y corregidos acordes de Entrada`"
        )
        # Registrar el siguiente paso para recibir los datos de versión
        bot.register_next_step_handler(msg, procesar_cambios_y_publicar)

    except Exception as e:
        bot.reply_to(message, f"❌ Error al procesar el PDF: {str(e)}")

def procesar_cambios_y_publicar(message):
    if not es_autorizado(message):
        return

    texto = message.text.strip()
    
    # Separar la versión y la descripción
    if " - " in texto:
        partes = texto.split(" - ", 1)
        tag_version = partes[0].strip()
        descripcion = partes[1].strip()
    else:
        tag_version = texto.split(" ")[0].strip()
        descripcion = "Actualización general del cancionero"

    bot.send_message(message.chat.id, "⏳ Realizando commit, etiquetando y subiendo los cambios a GitHub...")

    try:
        # Ejecutar los comandos de Git automáticamente
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", f"Actualización {tag_version}: {descripcion}"], check=True)
        subprocess.run(["git", "tag", "-a", tag_version, "-m", descripcion], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        subprocess.run(["git", "push", "origin", tag_version], check=True)

        # Generar el plantilla de mensaje para WhatsApp
        mensaje_whatsapp = (
            f"🎶 *CANCIONERO DEL CORO ACTUALIZADO* 🎶\n\n"
            f"📌 *Versión:* {tag_version}\n"
            f"📝 *Novedades:* {descripcion}\n\n"
            f"📖 *Consulta o descarga el cancionero en línea aquí:*\n"
            f"https://llumi2008.github.io/te-regalo-una-cancion/\n\n"
            f"¡Dios les bendiga!"
        )

        bot.send_message(
            message.chat.id, 
            f"✅ **¡Versión {tag_version} subida y publicada con éxito!**\n\n"
            f"📋 **Mensaje listo para copiar y pegar en WhatsApp:**\n\n"
            f"```\n{mensaje_whatsapp}\n```",
            parse_mode="Markdown"
        )

    except subprocess.CalledProcessError as e:
        bot.send_message(
            message.chat.id, 
            f"❌ **Error al ejecutar comandos de Git:**\n`{str(e)}`\n\n"
            f"Verifica que la terminal no tenga ningún proceso bloqueando la carpeta."
        )

print("🤖 Bot listo para procesar actualizaciones... Presiona Ctrl+C para detenerlo.")
bot.infinity_polling()
