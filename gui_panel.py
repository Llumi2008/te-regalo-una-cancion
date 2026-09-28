import os
import subprocess
import threading
import customtkinter as ctk
from tkinter import messagebox

# Configuración del tema visual
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AppPanel(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Panel de Control - Cancionero del Coro")
        self.geometry("600x550")
        self.resizable(False, False)

        self.bot_process = None

        # Título principal
        self.lbl_title = ctk.CTkLabel(
            self, 
            text="🎵 Gestor del Cancionero", 
            font=ctk.CTkFont(size=22, weight="bold")
        )
        self.lbl_title.pack(pady=15)

        # SECCIÓN 1: Estado y Control del Bot de Telegram
        self.frame_bot = ctk.CTkFrame(self)
        self.frame_bot.pack(fill="x", padx=20, pady=10)

        self.lbl_bot_status = ctk.CTkLabel(
            self.frame_bot, 
            text="Bot de Telegram: DETENIDO", 
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#ef4444"
        )
        self.lbl_bot_status.pack(side="left", padx=15, pady=15)

        self.btn_toggle_bot = ctk.CTkButton(
            self.frame_bot, 
            text="Iniciar Bot", 
            command=self.toggle_bot,
            fg_color="#22c55e",
            hover_color="#16a34a"
        )
        self.btn_toggle_bot.pack(side="right", padx=15, pady=15)

        # SECCIÓN 2: Sincronización rápida de archivos (.chrd, HTML, etc.)
        self.frame_sync = ctk.CTkFrame(self)
        self.frame_sync.pack(fill="x", padx=20, pady=10)

        self.lbl_sync = ctk.CTkLabel(
            self.frame_sync, 
            text="Respaldar cambios locales (.chrd, HTML, etc.)", 
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.lbl_sync.pack(anchor="w", padx=15, pady=(10, 5))

        self.entry_commit_msg = ctk.CTkEntry(
            self.frame_sync, 
            placeholder_text="Descripción del cambio (ej: Añadidos acordes de Gloria)"
        )
        self.entry_commit_msg.pack(fill="x", padx=15, pady=5)

        self.btn_sync = ctk.CTkButton(
            self.frame_sync, 
            text="⬆️ Subir cambios a GitHub", 
            command=self.sync_repository
        )
        self.btn_sync.pack(fill="x", padx=15, pady=(5, 15))

        # SECCIÓN 3: Gestión y Modificación de Tags / Versiones
        self.frame_tags = ctk.CTkFrame(self)
        self.frame_tags.pack(fill="x", padx=20, pady=10)

        self.lbl_tag = ctk.CTkLabel(
            self.frame_tags, 
            text="Modificar / Sobrescribir Tag o Descripción", 
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.lbl_tag.pack(anchor="w", padx=15, pady=(10, 5))

        self.entry_tag_name = ctk.CTkEntry(
            self.frame_tags, 
            placeholder_text="Nombre de la versión (ej: v1.1.1)"
        )
        self.entry_tag_name.pack(fill="x", padx=15, pady=5)

        self.entry_tag_desc = ctk.CTkEntry(
            self.frame_tags, 
            placeholder_text="Nueva descripción del Tag / Release"
        )
        self.entry_tag_desc.pack(fill="x", padx=15, pady=5)

        self.btn_update_tag = ctk.CTkButton(
            self.frame_tags, 
            text="🏷️ Actualizar Tag en GitHub", 
            command=self.update_git_tag,
            fg_color="#eab308",
            hover_color="#ca8a04",
            text_color="#000000"
        )
        self.btn_update_tag.pack(fill="x", padx=15, pady=(5, 15))

    # FUNCIONES DE CONTROL

    def toggle_bot(self):
        """Inicia o detiene la ejecución de bot.py en segundo plano."""
        if self.bot_process is None:
            if not os.path.exists("bot.py"):
                messagebox.showerror("Error", "No se encontró el archivo bot.py en esta carpeta.")
                return

            self.bot_process = subprocess.Popen(["python", "bot.py"])
            self.lbl_bot_status.configure(text="Bot de Telegram: EN EJECUCIÓN", text_color="#22c55e")
            self.btn_toggle_bot.configure(text="Detener Bot", fg_color="#ef4444", hover_color="#dc2626")
        else:
            self.bot_process.terminate()
            self.bot_process = None
            self.lbl_bot_status.configure(text="Bot de Telegram: DETENIDO", text_color="#ef4444")
            self.btn_toggle_bot.configure(text="Iniciar Bot", fg_color="#22c55e", hover_color="#16a34a")

    def sync_repository(self):
        """Sube todos los archivos modificados o creados (.chrd, etc.) a GitHub."""
        mensaje = self.entry_commit_msg.get().strip()
        if not mensaje:
            mensaje = "Actualización general de archivos"

        def run_sync():
            try:
                # 1. Guardar cambios locales primero en el área de ensayo
                subprocess.run(["git", "add", "."], capture_output=True, text=True, check=True)
                
                # 2. Hacer commit local para dejar limpia la zona de trabajo
                subprocess.run(["git", "commit", "-m", mensaje], capture_output=True, text=True)
                
                # 3. Traer actualizaciones del remoto y aplicar rebase
                subprocess.run(["git", "pull", "origin", "main", "--rebase"], capture_output=True, text=True, check=True)
                
                # 4. Enviar cambios finales a GitHub
                subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True, check=True)
                
                messagebox.showinfo("Éxito", "Archivos sincronizados y subidos a GitHub correctamente.")
                self.entry_commit_msg.delete(0, 'end')
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr.strip() if e.stderr else str(e)
                messagebox.showerror("Error de Git", f"No se pudieron subir los cambios:\n\n{error_msg}")

        threading.Thread(target=run_sync, daemon=True).start()

    def update_git_tag(self):
        """Reescribe o crea un tag con su texto descriptivo y lo fuerza en GitHub."""
        tag = self.entry_tag_name.get().strip()
        desc = self.entry_tag_desc.get().strip()

        if not tag or not desc:
            messagebox.showwarning("Campos vacíos", "Por favor ingresa tanto el nombre de la versión como la descripción.")
            return

        def run_tag_update():
            try:
                # 1. Asegurar commit local previo
                subprocess.run(["git", "add", "."], capture_output=True, text=True, check=True)
                subprocess.run(["git", "commit", "-m", f"Guardado previo a tag {tag}"], capture_output=True, text=True)

                # 2. Sincronizar historial remoto
                subprocess.run(["git", "pull", "origin", "main", "--rebase"], capture_output=True, text=True, check=True)
                
                # 3. Crear/reemplazar tag localmente
                subprocess.run(["git", "tag", "-fa", tag, "-m", desc], capture_output=True, text=True, check=True)
                
                # 4. Forzar actualización del tag remoto en GitHub
                subprocess.run(["git", "push", "origin", tag, "--force"], capture_output=True, text=True, check=True)
                
                messagebox.showinfo("Éxito", f"El tag '{tag}' ha sido actualizado correctamente en GitHub.")
                self.entry_tag_name.delete(0, 'end')
                self.entry_tag_desc.delete(0, 'end')
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr.strip() if e.stderr else str(e)
                messagebox.showerror("Error de Git", f"No se pudo actualizar el tag:\n\n{error_msg}")

        threading.Thread(target=run_tag_update, daemon=True).start()

if __name__ == "__main__":
    app = AppPanel()
    app.mainloop()
