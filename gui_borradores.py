import os
import json
import re
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

BASE_DIR = Path.home() / "CM_Borradores"
TRASH_DIR = BASE_DIR / "_PAPELERA"
INDEX_FILE = BASE_DIR / "index.jsonl"

TRASH_DIR.mkdir(parents=True, exist_ok=True)


def ts_to_hhmm(ts: str) -> str:
    ts = ts or ""
    if len(ts) >= 13 and "_" in ts:
        d, h = ts.split("_", 1)
        if len(d) == 8 and len(h) >= 6:
            return f"{d[0:4]}-{d[4:6]}-{d[6:8]} {h[0:2]}:{h[2:4]}"
    return ts


def fmt_precio(s: str) -> str:
    s = (s or "").strip()
    return re.sub(r"[^\d]", "", s)


def camel_to_phrase(token: str) -> str:
    token = (token or "").replace("#", "").strip()
    token = re.sub(r"[^A-Za-z0-9áéíóúñüÁÉÍÓÚÑÜ]", "", token)
    token = re.sub(r"([a-záéíóúñü])([A-ZÁÉÍÓÚÑÜ0-9])", r"\1 \2", token)
    token = re.sub(r"([0-9])([A-Za-záéíóúñüÁÉÍÓÚÑÜ])", r"\1 \2", token)
    token = re.sub(r"\s+", " ", token).strip().lower()
    token = re.sub(r"(20\d{2})(20\d{2})", r"\1 \2", token)
    return token


def normalize_keyword_line(line: str) -> str:
    """
    Mantiene frases completas.
    Solo convierte CamelCase/hashtags a frase normal.
    """
    s = (line or "").strip()
    s = s.replace("#", "")
    s = s.replace("•", " ").replace("|", " ").replace("—", " ")
    s = re.sub(r"\s+", " ", s).strip()

    if not s:
        return ""

    # Si ya tiene espacios, asumir que ya es frase
    if " " in s:
        return s.lower()

    # Si no tiene espacios, puede ser CamelCase / token pegado
    return camel_to_phrase(s)


def keywords_lines_from_block(kw_text: str, max_items: int = 16):
    """
    Convierte bloque de keywords en lista de FRASES.
    Respeta líneas ya formadas.
    """
    if not kw_text:
        return []

    raw_lines = [x.strip() for x in kw_text.splitlines() if x.strip()]
    out = []
    seen = set()

    # Caso 1: ya vienen en líneas separadas
    if len(raw_lines) >= 2:
        for line in raw_lines:
            phrase = normalize_keyword_line(line)
            phrase = re.sub(r"\s+", " ", phrase).strip()
            if not phrase:
                continue
            if len(phrase.split()) < 2:
                continue
            key = phrase.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(phrase)
            if len(out) >= max_items:
                break
        return out

    # Caso 2: viene todo pegado en una sola línea
    one = raw_lines[0] if raw_lines else ""
    one = one.replace("#", " ")
    one = re.sub(r"[|•,;]+", " ", one)
    one = re.sub(r"\s+", " ", one).strip()

    if not one:
        return []

    tokens = one.split(" ")

    i = 0
    while i < len(tokens):
        tok = tokens[i].strip()
        if not tok:
            i += 1
            continue

        # si token ya tiene camel case, convertirlo
        phrase = normalize_keyword_line(tok)

        # si quedó de una sola palabra, intentar agrupar 2-4 palabras
        if len(phrase.split()) < 2:
            chunk = [tok]
            j = i + 1
            while j < len(tokens) and len(chunk) < 4:
                nxt = tokens[j].strip()
                if not nxt:
                    j += 1
                    continue
                # cortar si el siguiente parece nueva frase camelcase grande
                if re.search(r"[A-ZÁÉÍÓÚÑÜ]", nxt) and len(chunk) >= 2:
                    break
                chunk.append(nxt)
                j += 1

            phrase = " ".join(chunk).lower()
            i = j
        else:
            i += 1

        phrase = re.sub(r"\s+", " ", phrase).strip()
        if not phrase:
            continue
        if len(phrase.split()) < 2:
            continue

        key = phrase.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(phrase)

        if len(out) >= max_items:
            break

    return out


def has_keywords_header(lines: list[str]):
    for i, l in enumerate(lines):
        if l.strip().lower().startswith("palabras clave"):
            return i
    return None


def looks_like_keywords_line(line: str) -> bool:
    s = (line or "").strip()
    if not s:
        return False
    if "#" in s:
        return True
    if len(s.split()) >= 8:
        return True
    camel_hits = len(re.findall(r"[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]+", s))
    return camel_hits >= 4


def limpiar_y_convertir_keywords(texto: str) -> str:
    """
    Regla importante:
    - si las keywords ya están una por línea, NO romperlas
    - solo normalizar hashtags / CamelCase
    """
    if not texto:
        return ""

    texto = texto.replace("#", "")
    lines = texto.splitlines()

    idx = has_keywords_header(lines)
    if idx is not None:
        head = "\n".join(lines[:idx]).rstrip()
        tail = "\n".join(lines[idx + 1:]).strip()
        phrases = keywords_lines_from_block(tail, 16)
        return (head + "\n\nPalabras clave:\n" + "\n".join(phrases)).strip() + "\n"

    non_empty = [(i, l) for i, l in enumerate(lines) if l.strip()]
    if not non_empty:
        return texto.strip() + "\n"

    last = non_empty[-1][0]
    start = max(0, last - 5)

    kw_start = None
    for i in range(last, start - 1, -1):
        if looks_like_keywords_line(lines[i]):
            kw_start = i
        else:
            if kw_start is not None:
                break

    if kw_start is None:
        return texto.strip() + "\n"

    head = "\n".join(lines[:kw_start]).rstrip()
    kw_block = "\n".join(lines[kw_start:last + 1]).strip()
    phrases = keywords_lines_from_block(kw_block, 16)

    return (head + "\n\nPalabras clave:\n" + "\n".join(phrases)).strip() + "\n"


class ScrollFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        canvas = tk.Canvas(self, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self.inner = tk.Frame(canvas)
        self.inner_id = canvas.create_window((0, 0), window=self.inner, anchor="nw")

        def _on_configure(_e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(self.inner_id, width=canvas.winfo_width())

        self.inner.bind("<Configure>", _on_configure)

        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Crazy Motors — Borradores Marketplace")

        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{int(sw*0.92)}x{int(sh*0.90)}+10+10")

        self.row_to_record = {}
        self.current_record = None

        top = tk.Frame(root)
        top.pack(fill="x", padx=6, pady=6)

        tk.Label(top, text="Buscar:").pack(side="left")
        self.search = tk.Entry(top)
        self.search.pack(side="left", fill="x", expand=True, padx=(6, 10))
        self.search.bind("<KeyRelease>", lambda e: self.reload())

        tk.Label(top, text="Filtro:").pack(side="left", padx=(0, 4))
        self.filter_status = tk.StringVar(value="Todos")
        self.filter_combo = ttk.Combobox(
            top,
            textvariable=self.filter_status,
            values=["Todos", "Pendientes", "Publicados"],
            state="readonly",
            width=12
        )
        self.filter_combo.pack(side="left")
        self.filter_combo.bind("<<ComboboxSelected>>", lambda e: self.reload())

        tk.Button(top, text="Recargar", command=self.reload).pack(side="right", padx=4)
        tk.Button(top, text="Abrir carpeta base", command=self.open_base).pack(side="right", padx=4)
        tk.Button(top, text="Salir", command=root.quit).pack(side="right", padx=4)

        main = tk.PanedWindow(root, orient="horizontal", sashrelief="raised")
        main.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        left = tk.Frame(main)
        main.add(left, minsize=560)

        tk.Label(left, text="Publicaciones").pack(anchor="w")

        self.tree = ttk.Treeview(
            left,
            columns=("fecha", "producto", "marca", "linea", "anio", "precio", "estado", "perfil", "pub"),
            show="headings",
        )
        self.tree.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)

        cols = [
            ("fecha", "Fecha/Hora", 120, "w"),
            ("producto", "Producto", 190, "w"),
            ("marca", "Marca", 90, "w"),
            ("linea", "Línea", 90, "w"),
            ("anio", "Año", 80, "w"),
            ("precio", "Precio", 70, "e"),
            ("estado", "Estado", 120, "w"),
            ("perfil", "Perfil", 140, "w"),
            ("pub", "Publicado", 80, "center"),
        ]
        for col, title, width, anchor in cols:
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor=anchor)

        self.tree.bind("<<TreeviewSelect>>", self.load_selected)

        right_wrap = ScrollFrame(main)
        main.add(right_wrap, minsize=640)
        right = right_wrap.inner

        fields = tk.Frame(right)
        fields.pack(fill="x", pady=(0, 6))

        self.producto = self.make_field(fields, "Producto", 0, 28)
        self.marca = self.make_field(fields, "Marca", 1, 14)
        self.linea = self.make_field(fields, "Línea", 2, 14)
        self.anio = self.make_field(fields, "Año", 3, 10)
        self.precio = self.make_field(fields, "Precio", 4, 10)
        self.estado = self.make_field(fields, "Estado", 5, 16)

        perf_row = tk.Frame(right)
        perf_row.pack(fill="x", pady=(0, 6))
        tk.Label(perf_row, text="Perfil donde se publicó:").pack(side="left")
        self.perfil = tk.Entry(perf_row, width=32)
        self.perfil.pack(side="left", padx=8)
        self.perfil.bind("<Return>", self.save_perfil_event)
        self.perfil.bind("<FocusOut>", self.save_perfil_event)

        sw_row = tk.Frame(right)
        sw_row.pack(fill="x", pady=(0, 6))
        tk.Label(sw_row, text="Estado de publicación:").pack(side="left", padx=(0, 8))

        self.switch_btn = tk.Button(
            sw_row,
            text="PENDIENTE",
            relief="raised",
            padx=18,
            pady=6,
            command=self.toggle_published,
            bg="#d9d9d9",
            fg="black",
        )
        self.switch_btn.pack(side="left")
        tk.Label(sw_row, text="(click para cambiar)").pack(side="left", padx=8)

        btns = tk.Frame(right)
        btns.pack(fill="x", pady=(0, 6))

        tk.Button(btns, text="Copiar borrador", command=self.copy).pack(side="left", padx=4)
        tk.Button(btns, text="Abrir carpeta", command=self.open_folder).pack(side="left", padx=4)
        tk.Button(btns, text="Abrir foto", command=self.open_photo).pack(side="left", padx=4)
        tk.Button(btns, text="Guardar cambios", command=self.save).pack(side="left", padx=4)
        tk.Button(btns, text="Renombrar", command=self.rename).pack(side="left", padx=4)
        tk.Button(btns, text="Borrar (papelera)", command=self.delete_to_trash).pack(side="left", padx=4)
        tk.Button(btns, text="Abrir papelera", command=self.open_trash).pack(side="left", padx=4)

        tip = tk.Label(
            right,
            text="Tip: el GUI respeta frases completas en Palabras clave. Borrar mueve a _PAPELERA.",
            anchor="w",
        )
        tip.pack(fill="x")

        self.img_label = tk.Label(right)
        self.img_label.pack(anchor="w", pady=(6, 6))

        self.text = tk.Text(right, wrap="word", height=18)
        self.text.pack(fill="both", expand=True)

        self.reload()

    def make_field(self, parent, label, col, width):
        tk.Label(parent, text=label).grid(row=0, column=col, sticky="w", padx=4)
        e = tk.Entry(parent, width=width)
        e.grid(row=1, column=col, sticky="w", padx=4)
        return e

    def read_index(self):
        if not INDEX_FILE.exists():
            return []
        out = []
        with INDEX_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
        return out

    def read_datos_from_folder(self, folder: Path, fallback: dict) -> dict:
        try:
            p = folder / "datos.json"
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
        return fallback or {}

    def write_datos(self, folder: Path, datos: dict):
        (folder / "datos.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")

    def set_switch_ui(self, published: bool):
        if published:
            self.switch_btn.configure(text="PUBLICADO", bg="#2e7d32", fg="white")
        else:
            self.switch_btn.configure(text="PENDIENTE", bg="#d9d9d9", fg="black")

    def reload(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.row_to_record = {}

        records = sorted(self.read_index(), key=lambda r: r.get("ts", ""), reverse=True)
        q = (self.search.get() or "").strip().lower()
        filtro = self.filter_status.get()

        for r in records:
            folder = Path(r.get("folder", ""))
            if not folder.exists():
                continue

            datos = self.read_datos_from_folder(folder, r.get("datos", {}) or {})

            ts = r.get("ts", "")
            fecha = ts_to_hhmm(ts)

            producto = (datos.get("producto") or "").strip()
            marca = (datos.get("marca") or "").strip()
            linea = (datos.get("linea") or "").strip()
            anio = (datos.get("anio") or "").strip()
            precio = fmt_precio(datos.get("precio") or "")
            estado = (datos.get("estado") or "").strip()
            perfil = (datos.get("perfil") or "").strip()

            publicado = bool(datos.get("publicado", False))
            pub_txt = "Sí" if publicado else "No"

            if filtro == "Pendientes" and publicado:
                continue
            if filtro == "Publicados" and not publicado:
                continue

            blob = " ".join([fecha, producto, marca, linea, anio, precio, estado, perfil, pub_txt]).lower()
            if q and q not in blob:
                continue

            r["datos"] = datos
            iid = self.tree.insert("", "end", values=(fecha, producto, marca, linea, anio, precio, estado, perfil, pub_txt))
            self.row_to_record[iid] = r

    def get_selected_record(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.row_to_record.get(sel[0])

    def load_selected(self, _event=None):
        r = self.get_selected_record()
        if not r:
            self.current_record = None
            return

        self.current_record = r
        folder = Path(r.get("folder", ""))
        datos = self.read_datos_from_folder(folder, r.get("datos", {}))
        r["datos"] = datos

        self.producto.delete(0, tk.END); self.producto.insert(0, datos.get("producto", ""))
        self.marca.delete(0, tk.END); self.marca.insert(0, datos.get("marca", ""))
        self.linea.delete(0, tk.END); self.linea.insert(0, datos.get("linea", ""))
        self.anio.delete(0, tk.END); self.anio.insert(0, datos.get("anio", ""))
        self.precio.delete(0, tk.END); self.precio.insert(0, fmt_precio(datos.get("precio", "")))
        self.estado.delete(0, tk.END); self.estado.insert(0, datos.get("estado", ""))

        self.perfil.delete(0, tk.END)
        self.perfil.insert(0, datos.get("perfil", ""))

        pub = bool(datos.get("publicado", False))
        self.set_switch_ui(pub)

        borr_path = Path(r.get("borrador", ""))
        borrador = borr_path.read_text(encoding="utf-8", errors="ignore") if borr_path.exists() else ""
        borrador = limpiar_y_convertir_keywords(borrador)

        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, borrador)

        self.img_label.configure(image=None)
        self.img_label.image = None
        thumb = Path(r.get("thumb", ""))
        if thumb.exists():
            try:
                img = Image.open(thumb)
                img.thumbnail((700, 700))
                img_tk = ImageTk.PhotoImage(img)
                self.img_label.configure(image=img_tk)
                self.img_label.image = img_tk
            except Exception:
                pass

    def save_perfil_event(self, _event=None):
        self.save_perfil_only()

    def save_perfil_only(self):
        if not self.current_record:
            return
        folder = Path(self.current_record.get("folder", ""))
        if not folder.exists():
            return

        datos = self.read_datos_from_folder(folder, self.current_record.get("datos", {}))
        datos["perfil"] = (self.perfil.get() or "").strip()
        if "publicado" not in datos:
            datos["publicado"] = False

        self.write_datos(folder, datos)
        self.current_record["datos"] = datos
        self.reload()

    def toggle_published(self):
        if not self.current_record:
            return

        folder = Path(self.current_record.get("folder", ""))
        if not folder.exists():
            messagebox.showerror("Error", "No existe la carpeta del borrador.")
            return

        datos = self.read_datos_from_folder(folder, self.current_record.get("datos", {}))
        datos["publicado"] = not bool(datos.get("publicado", False))
        datos["perfil"] = (self.perfil.get() or "").strip()

        self.write_datos(folder, datos)
        self.current_record["datos"] = datos

        self.set_switch_ui(bool(datos["publicado"]))
        self.reload()

    def save(self):
        r = self.get_selected_record()
        if not r:
            return

        folder = Path(r.get("folder", ""))
        if not folder.exists():
            messagebox.showerror("Error", "No existe la carpeta del borrador.")
            return

        texto = self.text.get("1.0", tk.END)
        texto = limpiar_y_convertir_keywords(texto)
        (folder / "borrador.txt").write_text(texto, encoding="utf-8")

        old = self.read_datos_from_folder(folder, r.get("datos", {}))

        datos = {
            "producto": (self.producto.get() or "").strip(),
            "marca": (self.marca.get() or "").strip(),
            "linea": (self.linea.get() or "").strip(),
            "anio": (self.anio.get() or "").strip(),
            "precio": fmt_precio(self.precio.get() or ""),
            "estado": (self.estado.get() or "").strip(),
            "publicado": bool(old.get("publicado", False)),
            "perfil": (self.perfil.get() or "").strip(),
        }
        self.write_datos(folder, datos)
        r["datos"] = datos

        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, texto)

        messagebox.showinfo("OK", "Guardado.")
        self.reload()

    def rename(self):
        r = self.get_selected_record()
        if not r:
            return

        folder = Path(r.get("folder", ""))
        if not folder.exists():
            messagebox.showerror("Error", "No existe la carpeta del borrador.")
            return

        ts = r.get("ts", "")
        prod = (self.producto.get() or "").strip().lower()
        prod = re.sub(r"\s+", "-", prod)
        prod = re.sub(r"[^a-z0-9áéíóúñü\-]", "", prod)
        prod = re.sub(r"-+", "-", prod).strip("-")[:60] or "producto"

        new_folder = BASE_DIR / f"{ts}_{prod}"
        if new_folder.exists():
            messagebox.showerror("Error", "Ya existe una carpeta con ese nombre.")
            return

        shutil.move(str(folder), str(new_folder))

        new_record = dict(r)
        new_record["folder"] = str(new_folder)
        new_record["foto"] = str(new_folder / "foto.jpg")
        new_record["thumb"] = str(new_folder / "thumb.jpg")
        new_record["borrador"] = str(new_folder / "borrador.txt")

        with INDEX_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(new_record, ensure_ascii=False) + "\n")

        messagebox.showinfo("OK", "Renombrado.")
        self.reload()

    def delete_to_trash(self):
        r = self.get_selected_record()
        if not r:
            return

        folder = Path(r.get("folder", ""))
        if not folder.exists():
            messagebox.showerror("Error", "No existe la carpeta del borrador.")
            return

        if not messagebox.askyesno(
            "Mover a papelera",
            f"¿Mover este borrador a la papelera?\n\n{folder.name}\n\nNo se eliminará definitivamente."
        ):
            return

        target = TRASH_DIR / folder.name
        if target.exists():
            suffix = Path(folder).name + "_" + Path(folder).stem
            target = TRASH_DIR / f"{folder.name}_{suffix}"

        shutil.move(str(folder), str(target))
        messagebox.showinfo("OK", f"Movido a papelera:\n{target}")
        self.reload()

    def copy(self):
        texto = self.text.get("1.0", tk.END)
        texto = limpiar_y_convertir_keywords(texto)
        self.root.clipboard_clear()
        self.root.clipboard_append(texto)

    def open_folder(self):
        r = self.get_selected_record()
        if not r:
            return
        folder = r.get("folder", "")
        if folder:
            os.system(f'xdg-open "{folder}"')

    def open_photo(self):
        r = self.get_selected_record()
        if not r:
            return
        foto = r.get("foto", "")
        if foto:
            os.system(f'xdg-open "{foto}"')

    def open_base(self):
        os.system(f'xdg-open "{BASE_DIR}"')

    def open_trash(self):
        os.system(f'xdg-open "{TRASH_DIR}"')


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
