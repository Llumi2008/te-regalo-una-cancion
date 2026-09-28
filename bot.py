import os
import re
import subprocess
import requests
from dotenv import load_dotenv
import telebot
from telebot import types

# Cargar variables de entorno
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

REPO_OWNER = "Llumi2008"
REPO_NAME = "te-regalo-una-cancion"

if not TOKEN or not CHAT_ID:
    raise ValueError("Faltan variables en el archivo .env (TELEGRAM_TOKEN o TELEGRAM_CHAT_ID)")

bot = telebot.TeleBot(TOKEN)
user_data = {}

def es_autorizado(message_or_call):
    chat_id = message_or_call.chat.id if hasattr(message_or_call, 'chat') else message_or_call.message.chat.id
    return str(chat_id) == str(CHAT_ID)

def obtener_ultima_version():
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

def crear_github_release(tag_name, release_name, body_text, pdf_path=None):
    """Crea un Release oficial en GitHub usando la API REST."""
    if not GITHUB_TOKEN:
        return False, "GITHUB_TOKEN no configurado en .env (se usó git tag estándar)"

    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    data = {
        "tag_name": tag_name,
        "target_commitish": "main",
        "name": f"Cancionero {tag_name}",
        "body": body_text,
        "draft": False,
        "prerelease": False
    }

    response = requests.post(url, json=data, headers=headers)
    if response.status_code in [200, 201]:
        release_info = response.json()
        upload_url = release_info.get("upload_url", "").split("{")[0]

        # Adjuntar opcionalmente el PDF como Asset en el Release
        if pdf_path and os.path.exists(pdf_path) and upload_url:
            asset_headers = headers.copy()
            asset_headers["Content-Type"] = "application/pdf"
            with open(pdf_path, "rb") as f:
                requests.post(
                    f"{upload_url}?name=te_doy_una_cancion.pdf",
                    headers=asset_headers,
                    data=f
                )
        return True, "Release publicado exitosamente en GitHub"
    else:
        return False, f"API Error ({response.status_code}): {response.text}"

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if not es_autorizado(message):
        return
    bot.reply_to(
        message, 
        "👋 ¡Hola! Envíame el nuevo archivo PDF del cancionero para iniciar la actualización."
    )

@bot.message_handler(content_types=['document'])
def handle_pdf(message):
    if not es_autorizado(message):
        return

    if not message.document.file_name.lower().endswith('.pdf'):
        bot.reply_to(message, "⚠️ El archivo enviado debe ser un .pdf")
        return

    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        os.makedirs("pdf", exist_ok=True)
        pdf_path = os.path.join("pdf", "te doy una cancion.pdf")

        with open(pdf_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        version_actual = obtener_ultima_version()
        v_patch = calcular_siguiente_version(version_actual, 'patch')
        v_minor = calcular_siguiente_version(version_actual, 'minor')
        v_major = calcular_siguiente_version(version_actual, 'major')

        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_patch = types.InlineKeyboardButton(f"🔧 Corrección menor/acordes ({v_patch})", callback_data=f"ver:{v_patch}")
        btn_minor = types.InlineKeyboardButton(f"🎶 Nuevas canciones / cambios ({v_minor})", callback_data=f"ver:{v_minor}")
        btn_major = types.InlineKeyboardButton(f"🚀 Edición o cambio mayor ({v_major})", callback_data=f"ver:{v_major}")
        markup.add(btn_patch, btn_minor, btn_major)

        bot.reply_to(
            message,
            f"📄 **PDF guardado correctamente.**\n\n"
            f"📌 Última versión registrada: **{version_actual}**\n\n"
            f"Selecciona la versión a publicar:",
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
        text=f"✅ Versión seleccionada: **{nueva_version}**\n\n"
             f"Escribe la descripción/notas del cambio para la publicación (puedes enviar varias líneas):",
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

    bot.send_message(chat_id, f"⏳ Registrando tag **{tag_version}** y subiendo a GitHub...")

    pdf_path = os.path.join("pdf", "te doy una cancion.pdf")

    try:
        # 1. Hacer commit de los archivos
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", f"Actualización {tag_version}: {descripcion}"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)

        # 2. Crear el Tag anotado localmente
        subprocess.run(["git", "tag", "-a", tag_version, "-m", descripcion], check=True)
        subprocess.run(["git", "push", "origin", tag_version], check=True)

        # 3. Intentar publicar Release formal vía API si está el token
        release_exito, msg_release = crear_github_release(
            tag_name=tag_version,
            release_name=f"Cancionero {tag_version}",
            body_text=descripcion,
            pdf_path=pdf_path
        )

        # 4. Generar el mensaje formateado para WhatsApp
        mensaje_whatsapp = (
            f"🎶 *CANCIONERO DEL CORO ACTUALIZADO* 🎶\n\n"
            f"📌 *Versión:* {tag_version}\n"
            f"📝 *Novedades:*\n{descripcion}\n\n"
            f"📖 *Consulta o descarga el cancionero en línea aquí:*\n"
            f"https://llumi2008.github.io/te-regalo-una-cancion/\n\n"
            f"¡Dios les bendiga!"
        )

        bot.send_message(
            chat_id, 
            f"🎉 **¡Versión {tag_version} publicada con éxito!**\n\n"
            f"📌 **Detalle de Tag/Release:** {msg_release}\n\n"
            f"📋 **Mensaje listo para WhatsApp:**\n\n"
            f"```\n{mensaje_whatsapp}\n```",
            parse_mode="Markdown"
        )

    except subprocess.CalledProcessError as e:
        bot.send_message(
            chat_id, 
            f"❌ **Error al ejecutar comandos de Git:**\n`{str(e)}`"
        )

print("🤖 Bot actualizado listo... Presiona Ctrl+C para detenerlo.")
bot.infinity_polling()
