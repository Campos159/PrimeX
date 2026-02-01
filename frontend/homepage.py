import tkinter as tk
from tkinter import font, PhotoImage
import os
import urllib.request
import tempfile
import sys
import subprocess
import threading
import time

# Função para baixar a fonte Bebas Neue se não existir localmente
def download_bebas_neue():
    font_url = "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf"
    temp_dir = tempfile.gettempdir()
    font_path = os.path.join(temp_dir, "BebasNeue-Regular.ttf")
    if not os.path.exists(font_path):
        urllib.request.urlretrieve(font_url, font_path)
    return font_path

# Função para registrar a fonte no Windows (necessário para Tkinter reconhecer)
def register_font_windows(font_path):
    import ctypes
    FR_PRIVATE = 0x10
    ctypes.windll.gdi32.AddFontResourceExW(font_path, FR_PRIVATE, 0)

# Classe da janela de loading fullscreen com logo centralizada
class LoadingScreen(tk.Tk):
    def __init__(self):
        super().__init__()
        self.configure(bg="#282828")
        self.attributes("-fullscreen", True)
        self.title("Carregando...")

        # Carregar a imagem da logo e redimensionar para largura 600px
        logo_path = os.path.join("assets", "logos", "logo.png")
        logo_img = None
        if os.path.exists(logo_path):
            try:
                from PIL import Image, ImageTk
                img = Image.open(logo_path)
                base_width = 600
                w_percent = (base_width / float(img.size[0]))
                h_size = int((float(img.size[1]) * float(w_percent)))
                img = img.resize((base_width, h_size), Image.Resampling.LANCZOS)
                logo_img = ImageTk.PhotoImage(img)
            except ImportError:
                logo_img = PhotoImage(file=logo_path)

        # Label da logo centralizada
        if logo_img:
            label = tk.Label(self, image=logo_img, bg="#282828")
            label.image = logo_img  # manter referência para evitar garbage collection
            label.pack(expand=True)

def abrir_script_com_loading(script_name):
    # Fecha a janela principal imediatamente
    root.destroy()

    # Cria a janela de loading fullscreen
    loading = LoadingScreen()

    # Função para rodar o script filho e monitorar o processo
    def run_and_wait():
        # Abre o script filho
        proc = subprocess.Popen([sys.executable, script_name])

        # Aguarda um curto tempo para garantir que o processo iniciou a interface gráfica
        time.sleep(1)

        # Fecha a janela de loading assim que o script filho foi iniciado
        loading.destroy()

    # Executa o processo em thread separada para não travar a GUI do loading
    threading.Thread(target=run_and_wait, daemon=True).start()

    # Inicia o loop da janela de loading (bloqueante)
    loading.mainloop()

# Criar a janela principal
root = tk.Tk()
root.title("Gameprime Inicial")
root.configure(bg="#282828")

# Tornar a janela fullscreen
root.attributes("-fullscreen", True)

# Baixar e registrar a fonte Bebas Neue
font_path = download_bebas_neue()
if sys.platform == "win32":
    register_font_windows(font_path)

# Criar a fonte Bebas Neue tamanho grande para o título
try:
    bebas_neue_48 = font.Font(family="Bebas Neue", size=48)
    bebas_neue_24 = font.Font(family="Bebas Neue", size=24)
except tk.TclError:
    bebas_neue_48 = font.Font(family="Arial", size=48, weight="bold")
    bebas_neue_24 = font.Font(family="Arial", size=24, weight="bold")

# Configurar grid da root para centralizar conteúdo
root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=1)

container = tk.Frame(root, bg="#282828")
container.grid(row=0, column=0, sticky="nsew")

container.grid_rowconfigure(0, weight=1)
container.grid_rowconfigure(1, weight=0)
container.grid_rowconfigure(2, weight=0)
container.grid_rowconfigure(3, weight=0)
container.grid_rowconfigure(4, weight=1)
container.grid_columnconfigure(0, weight=1)

# Frame para logo, alinhado centralmente e com espaçamento controlado
logo_frame = tk.Frame(container, bg="#282828")
logo_frame.grid(row=1, column=0, pady=(0, 2), sticky="n")

# Carregar a imagem da logo e redimensionar para largura 600px
logo_path = os.path.join("assets", "logos", "logo.png")
logo_img = None
if os.path.exists(logo_path):
    try:
        from PIL import Image, ImageTk
        img = Image.open(logo_path)
        base_width = 600
        w_percent = (base_width / float(img.size[0]))
        h_size = int((float(img.size[1]) * float(w_percent)))
        img = img.resize((base_width, h_size), Image.Resampling.LANCZOS)
        logo_img = ImageTk.PhotoImage(img)
    except ImportError:
        logo_img = PhotoImage(file=logo_path)

# Label da logo
if logo_img:
    logo_label = tk.Label(logo_frame, image=logo_img, bg="#282828")
    logo_label.pack()

# Canvas para o ícone do usuário
canvas_size = 150
canvas = tk.Canvas(container, width=canvas_size, height=canvas_size, bg="#282828", highlightthickness=0)
canvas.grid(row=2, column=0, pady=(0, 20), sticky="n")

# Desenhar círculo externo
circle_margin = 15
circle_diameter = canvas_size - 2 * circle_margin
canvas.create_oval(circle_margin, circle_margin, circle_margin + circle_diameter, circle_margin + circle_diameter, outline="#0a72f0", width=6)

# Desenhar cabeça (círculo)
head_x1 = canvas_size/2 - 20
head_y1 = 35
head_x2 = canvas_size/2 + 20
head_y2 = 75
canvas.create_oval(head_x1, head_y1, head_x2, head_y2, fill="#0a72f0", outline="#0a72f0")

# Desenhar corpo (arco semicircular)
body_x1 = canvas_size/2 - 30
body_y1 = 65
body_x2 = canvas_size/2 + 30
body_y2 = 135
canvas.create_arc(body_x1, body_y1, body_x2, body_y2, start=0, extent=180, fill="#0a72f0", outline="#0a72f0")

# Botões "ENTRAR" e "CADASTRO"
btn_entrar = tk.Button(container, text="ENTRAR", fg="#0a72f0", bg="#282828", font=bebas_neue_24,
                       borderwidth=0, activebackground="#282828", activeforeground="#0a72f0", cursor="hand2",
                       command=lambda: abrir_script_com_loading("login.py"))
btn_entrar.grid(row=3, column=0, pady=(0, 10), sticky="n")

btn_cadastro = tk.Button(container, text="CADASTRO", fg="#0a72f0", bg="#282828", font=bebas_neue_24,
                        borderwidth=0, activebackground="#282828", activeforeground="#0a72f0", cursor="hand2",
                        command=lambda: abrir_script_com_loading("register.py"))
btn_cadastro.grid(row=4, column=0, sticky="n")

# Função para sair do fullscreen com ESC
def exit_fullscreen(event):
    root.attributes("-fullscreen", False)

root.bind("<Escape>", exit_fullscreen)

root.mainloop()