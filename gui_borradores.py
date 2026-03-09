# ~/cm_bot/gui_borradores.py
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

# =========================================================
# Configuración
# =========================================================
BASE_DIR = Path.home() / "cm_bot" / "borradores"
TRASH_DIR = BASE_DIR / "_PAPELERA"
BASE_DIR.mkdir(parents=True, exist_ok=True)
TRASH_DIR.mkdir(parents=True, exist_ok=True)

COLORS = {
    "bg": "#16181d",
    "panel": "#1f2329",
    "panel_2": "#262b33",
    "field": "#2d333b",
    "text": "#f0f3f6",
    "muted": "#9da7b3",
    "accent": "#3b82f6",
    "accent_2": "#2563eb",
    "border": "#343b45",
    "preview_bg": "#0f1318",
    "ok": "#16a34a",
    "warn": "#d97706",
}


# =========================================================
# Utilidades
# =========================================================
def clean(text: str) -> str:
    text = str(text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def read_json(path: Path, default=None):
    if default is None:
        default = {}
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def write_json(path: Path, data: dict):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_text(path: Path) -> str:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception:
        pass
    return ""


def write_text(path: Path, text: str):
    path.write_text(text, encoding="utf-8")


def parse_ts_from_folder(name: str) -> datetime | None:
    m = re.match(r"^(\d{8}_\d{6})_", name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d_%H%M%S")
    except Exception:
        return None


def ts_pretty(name: str) -> str:
    dt = parse_ts_from_folder(name)
    if not dt:
        return name
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def bool_from_any(v) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v or "").strip().lower()
    return s in {"1", "true", "si", "sí", "yes", "y"}


def safe_move_to_trash(folder: Path) -> Path:
    base_name = folder.name
    target = TRASH_DIR / base_name
    if not target.exists():
        shutil.move(str(folder), str(target))
        return target

    suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = TRASH_DIR / f"{base_name}_{suffix}"
    shutil.move(str(folder), str(target))
    return target


def find_image(folder: Path) -> Path | None:
    for name in ["foto.jpg", "foto.jpeg", "foto.png", "image.jpg", "image.png"]:
        p = folder / name
        if p.exists():
            return p

    for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
        files = list(folder.glob(ext))
        if files:
            return files[0]

    return None


def build_borrador_text(meta: dict, seo_text: str = "") -> str:
    producto = clean(meta.get("producto", ""))
    marca = clean(meta.get("marca", ""))
    linea = clean(meta.get("linea", ""))
    anio = clean(meta.get("anio", ""))
    motor = clean(meta.get("motor", ""))
    medida = clean(meta.get("medida", ""))
    precio = clean(meta.get("precio", ""))
    estado = clean(meta.get("estado", ""))
    perfil = clean(meta.get("perfil", ""))

    existing = seo_text.strip()
    if existing:
        return existing if existing.endswith("\n") else existing + "\n"

    titulo = clean(meta.get("titulo", ""))
    intro = clean(meta.get("intro", ""))
    descripcion = clean(meta.get("descripcion", ""))

    lines = []

    if titulo:
        lines.append(titulo)

    if intro:
        lines.append(intro)

    lines.append("✅ Datos del producto")
    if producto:
        lines.append(f"Producto: {producto}")

    vehiculo = " ".join([x for x in [marca, linea, anio] if x]).strip()
    if vehiculo:
        lines.append(f"Vehículo: {vehiculo}")

    if motor:
        lines.append(f"Motor: {motor}")

    if medida:
        lines.append(f"Detalle / medida: {medida}")

    if precio:
        lines.append(f"Precio: Q{precio}")

    if estado:
        lines.append(f"Estado: {estado}")

    if perfil:
        lines.append(f"Perfil: {perfil}")

    if descripcion:
        lines.append("")
        lines.append(descripcion)

    kws = meta.get("keywords", [])
    if isinstance(kws, list) and kws:
        lines.append("")
        lines.append("Palabras clave:")
        for kw in kws:
            kw = clean(kw)
            if kw:
                lines.append(kw)

    return "\n".join(lines).strip() + "\n"


def open_path(path: Path):
    if not path.exists():
        raise FileNotFoundError(str(path))

    if os.name == "nt":
        os.startfile(str(path))
    else:
        subprocess.Popen(["xdg-open", str(path)])


def reveal_in_folder(path: Path):
    if not path.exists():
        raise FileNotFoundError(str(path))
    folder = path if path.is_dir() else path.parent
    open_path(folder)


# =========================================================
# Carga de borradores
# =========================================================
def load_drafts() -> list[dict]:
    drafts = []

    for folder in BASE_DIR.iterdir():
        if not folder.is_dir():
            continue
        if folder.name.startswith("_"):
            continue

        datos_path = folder / "datos.json"
        borrador_path = folder / "borrador.txt"
        image_path = find_image(folder)

        meta = read_json(datos_path, {})
        text = read_text(borrador_path)

        producto = clean(meta.get("producto", ""))
        marca = clean(meta.get("marca", ""))
        linea = clean(meta.get("linea", ""))
        anio = clean(meta.get("anio", ""))
        precio = clean(meta.get("precio", ""))
        estado = clean(meta.get("estado", ""))
        perfil = clean(meta.get("perfil", ""))
        publicado = bool_from_any(meta.get("publicado", False))
        created_at = clean(meta.get("created_at", ""))

        search_blob = " ".join([
            folder.name,
            producto,
            marca,
            linea,
            anio,
            precio,
            estado,
            perfil,
            text,
        ]).lower()

        drafts.append({
            "folder": folder,
            "folder_name": folder.name,
            "datos_path": datos_path,
            "borrador_path": borrador_path,
            "image_path": image_path,
            "meta": meta,
            "text": text,
            "producto": producto,
            "marca": marca,
            "linea": linea,
            "anio": anio,
            "precio": precio,
            "estado": estado,
            "perfil": perfil,
            "publicado": publicado,
            "created_at": created_at,
            "search_blob": search_blob,
            "sort_dt": parse_ts_from_folder(folder.name) or datetime.min,
        })

    drafts.sort(key=lambda x: x["sort_dt"], reverse=True)
    return drafts


# =========================================================
# App
# =========================================================
class BorradoresApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Crazy Motors - Gestor de Borradores")
        self.root.geometry("1760x980")
        self.root.minsize(1500, 860)

        self.drafts = []
        self.filtered = []
        self.current = None

        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="todos")
        self.perfil_filter_var = tk.StringVar(value="")
        self.info_var = tk.StringVar(value="0 borradores")
        self.photo_path_var = tk.StringVar(value="-")

        self.current_pil_image = None
        self.current_photo = None

        self.configure_root()
        self.build_style()
        self.build_ui()
        self.refresh_list()

    def configure_root(self):
        self.root.configure(bg=COLORS["bg"])
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

    def build_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        default_font = ("Segoe UI", 10)
        title_font = ("Segoe UI", 11, "bold")
        small_font = ("Segoe UI", 9)

        style.configure(".", background=COLORS["bg"], foreground=COLORS["text"], font=default_font)
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Panel.TFrame", background=COLORS["panel"])

        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=default_font)
        style.configure("Panel.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=default_font)
        style.configure("Muted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=small_font)
        style.configure("Title.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=title_font)

        style.configure(
            "TEntry",
            fieldbackground=COLORS["field"],
            foreground=COLORS["text"],
            insertcolor=COLORS["text"],
            borderwidth=1,
            relief="flat",
            padding=6,
        )

        style.configure(
            "TCombobox",
            fieldbackground=COLORS["field"],
            foreground=COLORS["text"],
            padding=4,
        )

        style.configure("Primary.TButton", padding=8, font=("Segoe UI", 10, "bold"))
        style.configure("TButton", padding=7, font=default_font)

        style.configure(
            "Treeview",
            background=COLORS["panel_2"],
            fieldbackground=COLORS["panel_2"],
            foreground=COLORS["text"],
            rowheight=32,
            borderwidth=0,
            relief="flat",
            font=default_font,
        )
        style.configure(
            "Treeview.Heading",
            background=COLORS["panel"],
            foreground=COLORS["text"],
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padding=7,
        )
        style.map(
            "Treeview",
            background=[("selected", COLORS["accent"])],
            foreground=[("selected", "white")]
        )

    def build_ui(self):
        self.build_topbar()
        self.build_main()

    def build_topbar(self):
        top = ttk.Frame(self.root, padding=(14, 12, 14, 10))
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Buscar:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        search_entry = ttk.Entry(top, textvariable=self.search_var)
        search_entry.grid(row=0, column=1, sticky="ew")
        search_entry.bind("<KeyRelease>", lambda e: self.apply_filters())

        ttk.Label(top, text="Estado:").grid(row=0, column=2, sticky="w", padx=(14, 8))
        status_combo = ttk.Combobox(
            top,
            textvariable=self.status_var,
            values=["todos", "pendientes", "publicados"],
            state="readonly",
            width=14,
        )
        status_combo.grid(row=0, column=3, sticky="w")
        status_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        ttk.Label(top, text="Perfil:").grid(row=0, column=4, sticky="w", padx=(14, 8))
        perfil_entry = ttk.Entry(top, textvariable=self.perfil_filter_var, width=18)
        perfil_entry.grid(row=0, column=5, sticky="w")
        perfil_entry.bind("<KeyRelease>", lambda e: self.apply_filters())

        ttk.Button(top, text="Refrescar", command=self.refresh_list).grid(row=0, column=6, padx=(14, 8))
        ttk.Button(top, text="Limpiar filtros", command=self.clear_filters).grid(row=0, column=7)
        ttk.Label(top, textvariable=self.info_var).grid(row=0, column=8, padx=(16, 0), sticky="e")

    def build_main(self):
        main = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        main.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        # Panel izquierdo
        self.left_panel = ttk.Frame(main, style="Panel.TFrame", padding=12)
        self.left_panel.columnconfigure(0, weight=1)
        self.left_panel.rowconfigure(1, weight=1)
        main.add(self.left_panel, weight=8)

        # Contenedor derecho con scroll
        right_container = ttk.Frame(main, style="Panel.TFrame")
        right_container.columnconfigure(0, weight=1)
        right_container.rowconfigure(0, weight=1)
        main.add(right_container, weight=7)

        self.right_canvas = tk.Canvas(
            right_container,
            bg=COLORS["panel"],
            highlightthickness=0,
            bd=0,
            relief="flat"
        )
        self.right_canvas.grid(row=0, column=0, sticky="nsew")

        right_scroll = ttk.Scrollbar(
            right_container,
            orient="vertical",
            command=self.right_canvas.yview
        )
        right_scroll.grid(row=0, column=1, sticky="ns")

        self.right_canvas.configure(yscrollcommand=right_scroll.set)

        self.right_panel = ttk.Frame(self.right_canvas, style="Panel.TFrame", padding=14)
        self.right_panel.columnconfigure(1, weight=1)
        self.right_panel.columnconfigure(3, weight=1)

        self.right_canvas_window = self.right_canvas.create_window(
            (0, 0),
            window=self.right_panel,
            anchor="nw"
        )

        def _on_right_panel_configure(event=None):
            self.right_canvas.configure(scrollregion=self.right_canvas.bbox("all"))

        def _on_right_canvas_configure(event):
            self.right_canvas.itemconfigure(self.right_canvas_window, width=event.width)

        self.right_panel.bind("<Configure>", _on_right_panel_configure)
        self.right_canvas.bind("<Configure>", _on_right_canvas_configure)

        self.build_left_panel()
        self.build_right_panel()

        # Scroll con rueda
        self.bind_scroll_recursive(self.right_canvas)
        self.bind_scroll_recursive(self.right_panel)

    def bind_scroll_recursive(self, widget):
        def _on_mousewheel(event):
            if event.delta:
                self.right_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                if getattr(event, "num", None) == 4:
                    self.right_canvas.yview_scroll(-1, "units")
                elif getattr(event, "num", None) == 5:
                    self.right_canvas.yview_scroll(1, "units")

        widget.bind("<MouseWheel>", _on_mousewheel)
        widget.bind("<Button-4>", _on_mousewheel)
        widget.bind("<Button-5>", _on_mousewheel)

    def build_left_panel(self):
        ttk.Label(self.left_panel, text="Lista de borradores", style="Title.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )

        columns = ("fecha", "producto", "vehiculo", "precio", "estado", "perfil", "publicado")
        self.tree = ttk.Treeview(self.left_panel, columns=columns, show="headings")

        self.tree.heading("fecha", text="Fecha")
        self.tree.heading("producto", text="Producto")
        self.tree.heading("vehiculo", text="Vehículo")
        self.tree.heading("precio", text="Precio")
        self.tree.heading("estado", text="Estado")
        self.tree.heading("perfil", text="Perfil")
        self.tree.heading("publicado", text="Publicado")

        self.tree.column("fecha", width=160, anchor="w")
        self.tree.column("producto", width=220, anchor="w")
        self.tree.column("vehiculo", width=290, anchor="w")
        self.tree.column("precio", width=95, anchor="center")
        self.tree.column("estado", width=120, anchor="center")
        self.tree.column("perfil", width=120, anchor="center")
        self.tree.column("publicado", width=105, anchor="center")

        yscroll = ttk.Scrollbar(self.left_panel, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)

        self.tree.grid(row=1, column=0, sticky="nsew")
        yscroll.grid(row=1, column=1, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        self.tree.tag_configure("published", foreground=COLORS["ok"])
        self.tree.tag_configure("pending", foreground=COLORS["warn"])

    def build_right_panel(self):
        r = 0
        ttk.Label(self.right_panel, text="Editor del borrador", style="Title.TLabel").grid(
            row=r, column=0, columnspan=4, sticky="w", pady=(0, 12)
        )

        r += 1
        ttk.Label(self.right_panel, text="Carpeta:", style="Panel.TLabel").grid(row=r, column=0, sticky="w", pady=6)
        self.lbl_folder = ttk.Label(self.right_panel, text="-", style="Panel.TLabel")
        self.lbl_folder.grid(row=r, column=1, columnspan=3, sticky="w", pady=6)

        r += 1
        ttk.Label(self.right_panel, text="Producto:", style="Panel.TLabel").grid(row=r, column=0, sticky="w", pady=5)
        self.ent_producto = ttk.Entry(self.right_panel)
        self.ent_producto.grid(row=r, column=1, sticky="ew", padx=(0, 12), pady=5)

        ttk.Label(self.right_panel, text="Marca:", style="Panel.TLabel").grid(row=r, column=2, sticky="w", pady=5)
        self.ent_marca = ttk.Entry(self.right_panel)
        self.ent_marca.grid(row=r, column=3, sticky="ew", pady=5)

        r += 1
        ttk.Label(self.right_panel, text="Línea:", style="Panel.TLabel").grid(row=r, column=0, sticky="w", pady=5)
        self.ent_linea = ttk.Entry(self.right_panel)
        self.ent_linea.grid(row=r, column=1, sticky="ew", padx=(0, 12), pady=5)

        ttk.Label(self.right_panel, text="Año:", style="Panel.TLabel").grid(row=r, column=2, sticky="w", pady=5)
        self.ent_anio = ttk.Entry(self.right_panel)
        self.ent_anio.grid(row=r, column=3, sticky="ew", pady=5)

        r += 1
        ttk.Label(self.right_panel, text="Motor:", style="Panel.TLabel").grid(row=r, column=0, sticky="w", pady=5)
        self.ent_motor = ttk.Entry(self.right_panel)
        self.ent_motor.grid(row=r, column=1, sticky="ew", padx=(0, 12), pady=5)

        ttk.Label(self.right_panel, text="Medida:", style="Panel.TLabel").grid(row=r, column=2, sticky="w", pady=5)
        self.ent_medida = ttk.Entry(self.right_panel)
        self.ent_medida.grid(row=r, column=3, sticky="ew", pady=5)

        r += 1
        ttk.Label(self.right_panel, text="Precio:", style="Panel.TLabel").grid(row=r, column=0, sticky="w", pady=5)
        self.ent_precio = ttk.Entry(self.right_panel)
        self.ent_precio.grid(row=r, column=1, sticky="ew", padx=(0, 12), pady=5)

        ttk.Label(self.right_panel, text="Estado:", style="Panel.TLabel").grid(row=r, column=2, sticky="w", pady=5)
        self.ent_estado = ttk.Entry(self.right_panel)
        self.ent_estado.grid(row=r, column=3, sticky="ew", pady=5)

        r += 1
        ttk.Label(self.right_panel, text="Perfil:", style="Panel.TLabel").grid(row=r, column=0, sticky="w", pady=5)
        self.ent_perfil = ttk.Entry(self.right_panel)
        self.ent_perfil.grid(row=r, column=1, sticky="ew", padx=(0, 12), pady=5)

        self.var_publicado = tk.BooleanVar(value=False)
        self.chk_publicado = ttk.Checkbutton(self.right_panel, text="Publicado", variable=self.var_publicado)
        self.chk_publicado.grid(row=r, column=2, sticky="w", pady=5)

        self.lbl_created = ttk.Label(self.right_panel, text="-", style="Muted.TLabel")
        self.lbl_created.grid(row=r, column=3, sticky="e", pady=5)

        r += 1
        ttk.Label(self.right_panel, text="Ruta foto:", style="Panel.TLabel").grid(row=r, column=0, sticky="w", pady=(6, 4))
        self.lbl_photo_path = ttk.Label(self.right_panel, textvariable=self.photo_path_var, style="Muted.TLabel")
        self.lbl_photo_path.grid(row=r, column=1, columnspan=3, sticky="w", pady=(6, 4))

        r += 1
        tools = ttk.Frame(self.right_panel, style="Panel.TFrame")
        tools.grid(row=r, column=0, columnspan=4, sticky="ew", pady=(4, 12))

        ttk.Button(tools, text="Abrir foto", command=self.open_current_image).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(tools, text="Abrir carpeta", command=self.open_current_folder).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(tools, text="Copiar ruta foto", command=self.copy_image_path).grid(row=0, column=2, padx=(0, 8))

        r += 1
        ttk.Label(self.right_panel, text="Vista previa", style="Title.TLabel").grid(row=r, column=0, sticky="w", pady=(0, 8))

        r += 1
        preview_frame = tk.Frame(
            self.right_panel,
            bg=COLORS["preview_bg"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            bd=0,
            height=360,
        )
        preview_frame.grid(row=r, column=0, columnspan=4, sticky="ew", pady=(0, 12))
        preview_frame.grid_propagate(False)

        self.image_canvas = tk.Canvas(
            preview_frame,
            bg=COLORS["preview_bg"],
            highlightthickness=0,
            bd=0,
            relief="flat",
            height=360,
        )
        self.image_canvas.pack(fill="both", expand=True)
        self.image_canvas.bind("<Configure>", self.on_preview_resize)

        r += 1
        ttk.Label(self.right_panel, text="Borrador SEO", style="Title.TLabel").grid(row=r, column=0, sticky="w", pady=(0, 8))

        r += 1
        text_wrap = tk.Frame(
            self.right_panel,
            bg=COLORS["preview_bg"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            bd=0,
        )
        text_wrap.grid(row=r, column=0, columnspan=4, sticky="nsew")

        text_wrap.columnconfigure(0, weight=1)
        text_wrap.rowconfigure(0, weight=1)

        self.txt_borrador = tk.Text(
            text_wrap,
            wrap="word",
            height=16,
            bg=COLORS["preview_bg"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            font=("Consolas", 11),
            padx=12,
            pady=12,
            selectbackground=COLORS["accent"],
            bd=0,
        )
        self.txt_borrador.grid(row=0, column=0, sticky="nsew")

        txt_scroll = ttk.Scrollbar(text_wrap, orient="vertical", command=self.txt_borrador.yview)
        self.txt_borrador.configure(yscrollcommand=txt_scroll.set)
        txt_scroll.grid(row=0, column=1, sticky="ns")

        r += 1
        actions = ttk.Frame(self.right_panel, style="Panel.TFrame")
        actions.grid(row=r, column=0, columnspan=4, sticky="ew", pady=(14, 0))

        ttk.Button(actions, text="Guardar cambios", command=self.save_current, style="Primary.TButton").grid(row=0, column=0, padx=(0, 8))
        ttk.Button(actions, text="Reconstruir texto", command=self.rebuild_text).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(actions, text="Marcar publicado", command=lambda: self.set_publicado(True)).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(actions, text="Marcar pendiente", command=lambda: self.set_publicado(False)).grid(row=0, column=3, padx=(0, 8))
        ttk.Button(actions, text="Eliminar a papelera", command=self.delete_current).grid(row=0, column=4)

        self.right_canvas.configure(scrollregion=self.right_canvas.bbox("all"))
        self.bind_scroll_recursive(self.image_canvas)
        self.bind_scroll_recursive(self.txt_borrador)

    def clear_filters(self):
        self.search_var.set("")
        self.status_var.set("todos")
        self.perfil_filter_var.set("")
        self.apply_filters()

    def refresh_list(self):
        self.drafts = load_drafts()
        self.apply_filters()

    def apply_filters(self):
        query = clean(self.search_var.get()).lower()
        status = clean(self.status_var.get()).lower()
        perfil = clean(self.perfil_filter_var.get()).lower()

        self.filtered = []
        for item in self.drafts:
            if query and query not in item["search_blob"]:
                continue
            if perfil and perfil not in item["perfil"].lower():
                continue
            if status == "publicados" and not item["publicado"]:
                continue
            if status == "pendientes" and item["publicado"]:
                continue
            self.filtered.append(item)

        self.render_tree()
        self.info_var.set(f"{len(self.filtered)} borradores")

    def render_tree(self):
        current_folder = self.current["folder_name"] if self.current else None

        for iid in self.tree.get_children():
            self.tree.delete(iid)

        for idx, item in enumerate(self.filtered):
            vehiculo = " ".join([x for x in [item["marca"], item["linea"], item["anio"]] if x]).strip()
            publicado_text = "Publicado" if item["publicado"] else "Pendiente"
            tags = ("published",) if item["publicado"] else ("pending",)

            self.tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    ts_pretty(item["folder_name"]),
                    item["producto"],
                    vehiculo,
                    f"Q{item['precio']}" if item["precio"] else "",
                    item["estado"],
                    item["perfil"],
                    publicado_text,
                ),
                tags=tags,
            )

        if current_folder:
            for idx, item in enumerate(self.filtered):
                if item["folder_name"] == current_folder:
                    self.tree.selection_set(str(idx))
                    self.tree.focus(str(idx))
                    self.tree.see(str(idx))
                    return

        if self.filtered:
            self.tree.selection_set("0")
            self.tree.focus("0")
            self.tree.see("0")
            self.load_current(self.filtered[0])
        else:
            self.clear_editor()

    def on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if 0 <= idx < len(self.filtered):
            self.load_current(self.filtered[idx])

    def clear_editor(self):
        self.current = None
        self.lbl_folder.config(text="-")
        self.lbl_created.config(text="-")
        self.photo_path_var.set("-")

        for ent in [
            self.ent_producto, self.ent_marca, self.ent_linea, self.ent_anio,
            self.ent_motor, self.ent_medida, self.ent_precio, self.ent_estado,
            self.ent_perfil
        ]:
            ent.delete(0, tk.END)

        self.var_publicado.set(False)
        self.txt_borrador.delete("1.0", tk.END)
        self.current_pil_image = None
        self.current_photo = None
        self.draw_preview_placeholder("Sin imagen")

    def load_current(self, item: dict):
        self.current = item
        meta = item["meta"]

        self.lbl_folder.config(text=item["folder_name"])
        self.lbl_created.config(text=f"Creado: {clean(meta.get('created_at', '-')) or '-'}")

        self._set_entry(self.ent_producto, meta.get("producto", ""))
        self._set_entry(self.ent_marca, meta.get("marca", ""))
        self._set_entry(self.ent_linea, meta.get("linea", ""))
        self._set_entry(self.ent_anio, meta.get("anio", ""))
        self._set_entry(self.ent_motor, meta.get("motor", ""))
        self._set_entry(self.ent_medida, meta.get("medida", ""))
        self._set_entry(self.ent_precio, meta.get("precio", ""))
        self._set_entry(self.ent_estado, meta.get("estado", ""))
        self._set_entry(self.ent_perfil, meta.get("perfil", ""))
        self.var_publicado.set(bool_from_any(meta.get("publicado", False)))

        self.txt_borrador.delete("1.0", tk.END)
        self.txt_borrador.insert("1.0", item["text"])

        img_path = item.get("image_path")
        self.photo_path_var.set(str(img_path) if img_path else "-")
        self.load_image(img_path)

        self.root.after(50, lambda: self.right_canvas.yview_moveto(0))

    def _set_entry(self, entry: ttk.Entry, value: str):
        entry.delete(0, tk.END)
        entry.insert(0, clean(value))

    def draw_preview_placeholder(self, text="Sin imagen"):
        self.image_canvas.delete("all")
        w = max(1, self.image_canvas.winfo_width())
        h = max(1, self.image_canvas.winfo_height())

        self.image_canvas.create_rectangle(0, 0, w, h, fill=COLORS["preview_bg"], outline="")
        self.image_canvas.create_text(
            w // 2,
            h // 2,
            text=text,
            fill=COLORS["muted"],
            font=("Segoe UI", 12),
        )

    def load_image(self, path: Path | None):
        self.current_pil_image = None
        self.current_photo = None

        if not path or not path.exists():
            self.draw_preview_placeholder("Sin imagen")
            return

        try:
            self.current_pil_image = Image.open(path).convert("RGB")
            self.root.after(50, self.render_current_image)
        except Exception:
            self.current_pil_image = None
            self.draw_preview_placeholder("No se pudo cargar la imagen")

    def on_preview_resize(self, _event=None):
        self.render_current_image()

    def render_current_image(self):
        self.image_canvas.delete("all")

        canvas_w = max(1, self.image_canvas.winfo_width())
        canvas_h = max(1, self.image_canvas.winfo_height())

        self.image_canvas.create_rectangle(
            0, 0, canvas_w, canvas_h,
            fill=COLORS["preview_bg"],
            outline=""
        )

        if self.current_pil_image is None:
            self.draw_preview_placeholder("Sin imagen")
            return

        img = self.current_pil_image.copy()
        w, h = img.size

        if w <= 0 or h <= 0:
            self.draw_preview_placeholder("Imagen inválida")
            return

        pad = 16
        max_w = max(1, canvas_w - pad * 2)
        max_h = max(1, canvas_h - pad * 2)

        ratio = min(max_w / w, max_h / h)
        new_w = max(1, int(w * ratio))
        new_h = max(1, int(h * ratio))

        img = img.resize((new_w, new_h), Image.LANCZOS)
        self.current_photo = ImageTk.PhotoImage(img)

        x = canvas_w // 2
        y = canvas_h // 2

        self.image_canvas.create_image(x, y, image=self.current_photo, anchor="center")

        left = x - new_w // 2
        top = y - new_h // 2
        right = left + new_w
        bottom = top + new_h

        self.image_canvas.create_rectangle(
            left - 1, top - 1, right + 1, bottom + 1,
            outline=COLORS["border"],
            width=1
        )

    def get_editor_meta(self) -> dict:
        if not self.current:
            return {}

        old = dict(self.current["meta"])
        old["producto"] = clean(self.ent_producto.get())
        old["marca"] = clean(self.ent_marca.get())
        old["linea"] = clean(self.ent_linea.get())
        old["anio"] = clean(self.ent_anio.get())
        old["motor"] = clean(self.ent_motor.get())
        old["medida"] = clean(self.ent_medida.get())
        old["precio"] = clean(self.ent_precio.get())
        old["estado"] = clean(self.ent_estado.get())
        old["perfil"] = clean(self.ent_perfil.get())
        old["publicado"] = bool(self.var_publicado.get())
        old.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
        old.setdefault("folder", self.current["folder_name"])
        return old

    def save_current(self):
        if not self.current:
            messagebox.showwarning("Sin selección", "Selecciona un borrador primero.")
            return

        try:
            meta = self.get_editor_meta()
            borrador_text = self.txt_borrador.get("1.0", tk.END).rstrip() + "\n"
            write_json(self.current["datos_path"], meta)
            write_text(self.current["borrador_path"], borrador_text)
            self.refresh_list()
            messagebox.showinfo("Guardado", "Cambios guardados correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

    def rebuild_text(self):
        if not self.current:
            messagebox.showwarning("Sin selección", "Selecciona un borrador primero.")
            return

        meta = self.get_editor_meta()
        new_text = build_borrador_text(meta, seo_text="")
        self.txt_borrador.delete("1.0", tk.END)
        self.txt_borrador.insert("1.0", new_text)

    def set_publicado(self, value: bool):
        if not self.current:
            messagebox.showwarning("Sin selección", "Selecciona un borrador primero.")
            return
        self.var_publicado.set(value)
        self.save_current()

    def delete_current(self):
        if not self.current:
            messagebox.showwarning("Sin selección", "Selecciona un borrador primero.")
            return

        producto = clean(self.ent_producto.get()) or self.current["folder_name"]
        ok = messagebox.askyesno("Confirmar", f"¿Mover a papelera este borrador?\n\n{producto}")
        if not ok:
            return

        try:
            target = safe_move_to_trash(self.current["folder"])
            self.refresh_list()
            messagebox.showinfo("Papelera", f"Borrador movido a:\n{target.name}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo mover a papelera:\n{e}")

    def open_current_image(self):
        if not self.current or not self.current.get("image_path"):
            messagebox.showwarning("Sin foto", "Este borrador no tiene foto.")
            return
        try:
            open_path(self.current["image_path"])
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir la foto:\n{e}")

    def open_current_folder(self):
        if not self.current:
            messagebox.showwarning("Sin selección", "Selecciona un borrador primero.")
            return
        try:
            reveal_in_folder(self.current["folder"])
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir la carpeta:\n{e}")

    def copy_image_path(self):
        if not self.current or not self.current.get("image_path"):
            messagebox.showwarning("Sin foto", "Este borrador no tiene foto.")
            return
        path = str(self.current["image_path"])
        self.root.clipboard_clear()
        self.root.clipboard_append(path)
        self.root.update()
        messagebox.showinfo("Ruta copiada", path)


def main():
    root = tk.Tk()
    app = BorradoresApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
