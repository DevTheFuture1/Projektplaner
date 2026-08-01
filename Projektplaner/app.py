import customtkinter as ctk
import json
import os
import sys
import uuid
import subprocess
import webbrowser
import importlib.util
from datetime import datetime
from tkinter import messagebox, simpledialog, filedialog
 
 
def resource_path(relative_path):
    """Findet Dateien wie das Icon, egal ob als Skript oder als gebündelte .exe gestartet."""
    try:
        base_path = sys._MEIPASS  # von PyInstaller gesetzt, wenn als .exe gebündelt
    except AttributeError:
        # Nicht als .exe gebündelt: immer den Ordner DIESER Datei nutzen,
        # unabhängig davon, von wo aus das Skript gestartet wurde.
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)
 
 
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
 
APP_NAME = "Projektplaner"
STAR_COLOR = "#f5c518"
STAR_EMPTY_COLOR = "#555555"
 
 
# ---------------------------------------------------------------------------
# Speicherorte
# ---------------------------------------------------------------------------
def get_data_path():
    """Liefert einen sinnvollen Speicherort für die Daten (funktioniert unter Windows, macOS, Linux)."""
    if os.name == "nt":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~/.local/share")
    folder = os.path.join(base, APP_NAME)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "data.json")
 
 
DATA_PATH = get_data_path()
ADDONS_DIR = os.path.join(os.path.dirname(DATA_PATH), "addons")
os.makedirs(ADDONS_DIR, exist_ok=True)
 
 
def open_path(path):
    """Öffnet eine Datei oder einen Ordner mit dem Standardprogramm des Betriebssystems."""
    try:
        if os.name == "nt":
            os.startfile(path)  # noqa
        elif sys.platform == "darwin":
            subprocess.call(["open", path])
        else:
            subprocess.call(["xdg-open", path])
        return True
    except Exception as e:
        messagebox.showerror(APP_NAME, f"Konnte nicht geöffnet werden:\n{e}")
        return False
 
 
def open_attachment(att):
    """Öffnet einen Anhang - eine Datei mit dem Standardprogramm, oder einen Link im Browser."""
    if att.get("type") == "link":
        webbrowser.open(att["target"])
    else:
        if not os.path.exists(att["target"]):
            messagebox.showerror(APP_NAME, f"Datei nicht gefunden:\n{att['target']}")
            return
        open_path(att["target"])
 
 
# ---------------------------------------------------------------------------
# Daten laden/speichern + Migration alter Datenformate
# ---------------------------------------------------------------------------
def migrate_task(task):
    if "importance" not in task:
        old_priority = task.get("priority", "mittel")
        mapping = {"hoch": 5, "mittel": 3, "niedrig": 1}
        task["importance"] = mapping.get(old_priority, 3)
    task.setdefault("attachments", [])
    task.setdefault("notes", "")
    task.setdefault("due", task.get("due", ""))
    # Alte Anhänge (nur {"path", "name"}) auf neues Format {"type","target","name"} heben
    migrated_attachments = []
    for att in task["attachments"]:
        if "type" not in att:
            migrated_attachments.append({
                "type": "file",
                "target": att.get("path", ""),
                "name": att.get("name", os.path.basename(att.get("path", "")) or "Datei"),
            })
        else:
            migrated_attachments.append(att)
    task["attachments"] = migrated_attachments
    return task
 
 
def migrate_project(proj):
    proj.setdefault("importance", 3)
    proj["tasks"] = [migrate_task(t) for t in proj.get("tasks", [])]
    return proj
 
 
def load_data():
    if os.path.exists(DATA_PATH):
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["projects"] = [migrate_project(p) for p in data.get("projects", [])]
                return data
        except Exception:
            pass
    return {"projects": []}
 
 
def save_data(data):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
 
 
# ---------------------------------------------------------------------------
# Wiederverwendbares Sterne-Bewertungs-Widget
# ---------------------------------------------------------------------------
class StarRating(ctk.CTkFrame):
    def __init__(self, master, value=3, size=16, editable=True, on_change=None, **kwargs):
        super().__init__(master, fg_color="transparent")
        self.value = value
        self.editable = editable
        self.on_change = on_change
        self.size = size
        self.star_labels = []
        for i in range(5):
            lbl = ctk.CTkLabel(self, text="★", font=ctk.CTkFont(size=size), text_color=self._color_for(i))
            lbl.grid(row=0, column=i, padx=1)
            if editable:
                lbl.configure(cursor="hand2")
                lbl.bind("<Button-1>", lambda e, idx=i: self._set(idx + 1))
            self.star_labels.append(lbl)
 
    def _color_for(self, idx):
        return STAR_COLOR if idx < self.value else STAR_EMPTY_COLOR
 
    def _set(self, val):
        self.value = val
        for i, lbl in enumerate(self.star_labels):
            lbl.configure(text_color=self._color_for(i))
        if self.on_change:
            self.on_change(val)
 
    def set_value(self, val):
        self.value = val
        for i, lbl in enumerate(self.star_labels):
            lbl.configure(text_color=self._color_for(i))
 
 
# ---------------------------------------------------------------------------
# Addon-System
# ---------------------------------------------------------------------------
class AddonAPI:
    """Diese Klasse wird an jedes Addon übergeben. Sie ist die einzige Schnittstelle,
    über die ein Addon mit der App sprechen darf – so bleibt alles kontrollierbar."""
 
    def __init__(self, app):
        self._app = app
        self.actions = []  # Liste von {"label", "callback", "icon"}
 
    def add_action(self, label, callback, icon="🧩"):
        """Registriert einen Button im Addon-Center, der beim Klick 'callback(api)' aufruft."""
        self.actions.append({"label": label, "callback": callback, "icon": icon})
 
    def add_project_panel(self, render_func):
        """Registriert ein eigenes Widget, das direkt im Hauptbereich unter der
        Fortschrittsanzeige des ausgewählten Projekts erscheint.
        render_func(parent_frame, project) wird bei jeder Aktualisierung aufgerufen -
        das Addon baut sich dort mit CTk-Widgets sein eigenes UI-Element."""
        self._app.project_panel_hooks.append(render_func)
 
    def add_sidebar_badge(self, badge_func):
        """Registriert eine kleine Text-Kennzeichnung, die in der Projekt-Seitenleiste
        unter jedem Projekt erscheint. badge_func(project) muss einen String oder
        None (nichts anzeigen) zurückgeben."""
        self._app.sidebar_badge_hooks.append(badge_func)
 
    def get_data(self):
        return self._app.data
 
    def get_projects(self):
        return self._app.data["projects"]
 
    def get_selected_project(self):
        return self._app.get_selected_project()
 
    def save(self):
        save_data(self._app.data)
 
    def refresh(self):
        self._app.refresh_project_list()
        self._app.refresh_main_area()
 
    def show_info(self, title, message):
        messagebox.showinfo(title, message)
 
    def show_warning(self, title, message):
        messagebox.showwarning(title, message)
 
    def ask_string(self, title, prompt):
        return simpledialog.askstring(title, prompt)
 
    def ask_open_file(self, title="Datei auswählen"):
        return filedialog.askopenfilename(title=title)
 
    def ask_save_file(self, title="Speichern unter", defaultextension=".txt"):
        return filedialog.asksaveasfilename(title=title, defaultextension=defaultextension)
 
 
def load_addons(api):
    """Lädt alle .py-Dateien aus dem Addon-Ordner und ruft deren register(api)-Funktion auf.
    Gibt eine Liste von Ladeergebnissen zurück (für die Anzeige im Addon-Center)."""
    results = []
    if not os.path.isdir(ADDONS_DIR):
        return results
    for filename in sorted(os.listdir(ADDONS_DIR)):
        if not filename.endswith(".py"):
            continue
        addon_name = filename[:-3]
        full_path = os.path.join(ADDONS_DIR, filename)
        try:
            spec = importlib.util.spec_from_file_location(addon_name, full_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "register") and callable(module.register):
                module.register(api)
                results.append({"name": addon_name, "status": "ok", "error": None})
            else:
                results.append({
                    "name": addon_name, "status": "warn",
                    "error": "Keine register(api)-Funktion in der Datei gefunden."
                })
        except Exception as e:
            results.append({"name": addon_name, "status": "error", "error": str(e)})
    return results
 
 
EXAMPLE_ADDON_CODE = '''"""
Beispiel-Addon für den Projektplaner.
Kopiere diese Datei, benenne sie um und passe sie an - fertig ist dein eigenes Addon!
 
Jedes Addon ist eine ganz normale .py-Datei in diesem Ordner mit einer
Funktion register(api). Die App ruft diese Funktion beim Start automatisch auf.
"""
 
def register(api):
    # Registriert eine Aktion, die im Addon-Center als Button erscheint.
    api.add_action("Aktuelles Projekt als TXT exportieren", export_project, icon="📄")
 
 
def export_project(api):
    proj = api.get_selected_project()
    if not proj:
        api.show_warning("Kein Projekt", "Bitte zuerst ein Projekt auswaehlen.")
        return
 
    path = api.ask_save_file(title="Projekt exportieren", defaultextension=".txt")
    if not path:
        return
 
    lines = [f"Projekt: {proj['name']}", ""]
    for t in proj["tasks"]:
        status = "[x]" if t.get("done") else "[ ]"
        stars = "*" * t.get("importance", 3)
        lines.append(f"{status} {t['title']}  ({stars})")
 
    with open(path, "w", encoding="utf-8") as f:
        f.write("\\n".join(lines))
 
    api.show_info("Export fertig", f"Projekt wurde gespeichert unter:\\n{path}")
'''
 
 
# ---------------------------------------------------------------------------
# Task-Zeile
# ---------------------------------------------------------------------------
class TaskRow(ctk.CTkFrame):
    def __init__(self, master, task, on_toggle, on_delete, on_importance_change, on_open_attachments, **kwargs):
        super().__init__(master, fg_color="#242424", corner_radius=10)
        self.task = task
 
        self.check_var = ctk.BooleanVar(value=task.get("done", False))
        self.check = ctk.CTkCheckBox(
            self, text="", variable=self.check_var,
            command=lambda: on_toggle(task["id"], self.check_var.get()),
            width=24,
        )
        self.check.grid(row=0, column=0, padx=(12, 6), pady=10)
 
        title_color = "#7f8c8d" if task.get("done") else "#ffffff"
        self.title_label = ctk.CTkLabel(
            self, text=task["title"], text_color=title_color,
            font=ctk.CTkFont(size=14, weight="bold"), anchor="w"
        )
        self.title_label.grid(row=0, column=1, sticky="w", padx=6, pady=10)
 
        stars = StarRating(
            self, value=task.get("importance", 3), size=13, editable=True,
            on_change=lambda v: on_importance_change(task["id"], v)
        )
        stars.grid(row=0, column=2, padx=8, pady=10)
 
        due = task.get("due", "")
        due_label = ctk.CTkLabel(self, text=(f"📅 {due}" if due else ""), text_color="#a0a0a0", font=ctk.CTkFont(size=12))
        due_label.grid(row=0, column=3, padx=6, pady=10)
 
        has_notes = bool(task.get("notes", "").strip())
        attachments = task.get("attachments", [])
        n_files = sum(1 for a in attachments if a.get("type") != "link")
        n_links = sum(1 for a in attachments if a.get("type") == "link")
 
        combo_text = "📎"
        parts = []
        if n_files:
            parts.append(f"{n_files}📄")
        if n_links:
            parts.append(f"{n_links}🔗")
        if has_notes:
            parts.append("📝")
        if parts:
            combo_text = " ".join(parts)
 
        attach_btn = ctk.CTkButton(
            self, text=combo_text, width=90, height=28,
            fg_color="#333333" if not (attachments or has_notes) else "#2b6cb0",
            hover_color="#3b7dc4",
            command=lambda: on_open_attachments(task["id"])
        )
        attach_btn.grid(row=0, column=4, padx=6, pady=10)
 
        del_btn = ctk.CTkButton(
            self, text="✕", width=28, height=28, fg_color="transparent",
            hover_color="#c0392b", text_color="#e74c3c",
            command=lambda: on_delete(task["id"])
        )
        del_btn.grid(row=0, column=5, padx=(6, 12), pady=10)
 
        self.grid_columnconfigure(1, weight=1)
 
 
# ---------------------------------------------------------------------------
# Haupt-App
# ---------------------------------------------------------------------------
class ProjectPlannerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1200x760")
        self.minsize(980, 620)
 
        icon_path = resource_path("icon.ico")
        try:
            self.iconbitmap(icon_path)
        except Exception as e:
            # Icon-Datei fehlt oder Betriebssystem/Tk-Version unterstützt .ico nicht.
            # Diagnose wird auf der Konsole ausgegeben (sichtbar, wenn man "python app.py"
            # aus einer cmd.exe heraus startet statt per Doppelklick).
            print(f"[Icon-Warnung] Konnte '{icon_path}' nicht als Fenster-Icon laden: {e}")
            print(f"[Icon-Warnung] Existiert die Datei dort? {os.path.exists(icon_path)}")
 
        self.data = load_data()
        self.selected_project_id = None
        self.sort_mode = "importance"
        self.project_panel_hooks = []   # Addons können hier eigene Widgets im Hauptbereich einklinken
        self.sidebar_badge_hooks = []   # Addons können hier kleine Text-Badges pro Projekt einklinken
 
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
 
        self._build_sidebar()
        self._build_main_area()
 
        # Addons laden (nachdem die UI existiert, falls ein Addon sofort etwas anzeigen will)
        self.addon_api = AddonAPI(self)
        self.addon_results = load_addons(self.addon_api)
 
        self.refresh_project_list()
        if self.data["projects"]:
            self.select_project(self._sorted_projects()[0]["id"])
 
    # ---------------- Sidebar ----------------
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color="#1a1a1a")
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)
 
        header = ctk.CTkLabel(self.sidebar, text="📁 Projekte", font=ctk.CTkFont(size=20, weight="bold"))
        header.pack(pady=(24, 6), padx=20, anchor="w")
 
        sort_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        sort_frame.pack(padx=20, fill="x", pady=(0, 10))
        ctk.CTkLabel(sort_frame, text="Sortieren:", font=ctk.CTkFont(size=12), text_color="#aaaaaa").pack(side="left")
        self.sort_menu = ctk.CTkOptionMenu(
            sort_frame, values=["Wichtigkeit", "Name"], width=120, height=26,
            font=ctk.CTkFont(size=12), command=self._on_sort_change
        )
        self.sort_menu.set("Wichtigkeit")
        self.sort_menu.pack(side="right")
 
        self.project_list_frame = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", width=250)
        self.project_list_frame.pack(fill="both", expand=True, padx=10)
 
        new_btn = ctk.CTkButton(
            self.sidebar, text="+ Neues Projekt", height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.create_project
        )
        new_btn.pack(pady=(12, 8), padx=20, fill="x")
 
        addon_btn = ctk.CTkButton(
            self.sidebar, text="🧩 Addons", height=34, fg_color="#333333", hover_color="#444444",
            command=self.open_addon_center
        )
        addon_btn.pack(pady=(0, 16), padx=20, fill="x")
 
    def _on_sort_change(self, _value):
        self.sort_mode = "importance" if self.sort_menu.get() == "Wichtigkeit" else "name"
        self.refresh_project_list()
 
    def _sorted_projects(self):
        if self.sort_mode == "importance":
            return sorted(self.data["projects"], key=lambda p: (-p.get("importance", 3), p["name"].lower()))
        return sorted(self.data["projects"], key=lambda p: p["name"].lower())
 
    def refresh_project_list(self):
        for w in self.project_list_frame.winfo_children():
            w.destroy()
 
        for proj in self._sorted_projects():
            total = len(proj["tasks"])
            done = sum(1 for t in proj["tasks"] if t.get("done"))
            is_selected = proj["id"] == self.selected_project_id
 
            row = ctk.CTkFrame(
                self.project_list_frame,
                fg_color="#2b6cb0" if is_selected else "#242424",
                corner_radius=10
            )
            row.pack(fill="x", pady=5)
            row.grid_columnconfigure(0, weight=1)
 
            top_row = ctk.CTkFrame(row, fg_color="transparent")
            top_row.grid(row=0, column=0, sticky="ew", padx=(6, 4), pady=(6, 0))
            top_row.grid_columnconfigure(0, weight=1)
 
            btn = ctk.CTkButton(
                top_row, text=proj["name"], anchor="w", fg_color="transparent",
                hover_color=("#3b7dc4" if is_selected else "#333333"),
                font=ctk.CTkFont(size=14, weight="bold"),
                command=lambda pid=proj["id"]: self.select_project(pid)
            )
            btn.grid(row=0, column=0, sticky="ew")
 
            sub = ctk.CTkLabel(top_row, text=f"{done}/{total}", text_color="#cccccc", font=ctk.CTkFont(size=11))
            sub.grid(row=0, column=1, padx=(4, 2))
 
            stars = StarRating(
                row, value=proj.get("importance", 3), size=11, editable=True,
                on_change=lambda v, pid=proj["id"]: self.set_project_importance(pid, v)
            )
            stars.grid(row=1, column=0, sticky="w", padx=10, pady=(2, 2))
 
            # Von Addons registrierte Badges anzeigen (z.B. Budget-Stand)
            badge_texts = []
            for badge_func in self.sidebar_badge_hooks:
                try:
                    text = badge_func(proj)
                    if text:
                        badge_texts.append(text)
                except Exception as e:
                    print(f"[Addon-Badge-Fehler] {e}")
            if badge_texts:
                badge_label = ctk.CTkLabel(
                    row, text="   ·   ".join(badge_texts), text_color="#9fb8d9",
                    font=ctk.CTkFont(size=10), anchor="w"
                )
                badge_label.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 8))
            else:
                ctk.CTkFrame(row, fg_color="transparent", height=6).grid(row=2, column=0)
 
    def create_project(self):
        dialog = ctk.CTkInputDialog(text="Name des neuen Projekts:", title="Neues Projekt")
        name = dialog.get_input()
        if name:
            new_proj = {"id": str(uuid.uuid4()), "name": name, "tasks": [], "importance": 3}
            self.data["projects"].append(new_proj)
            save_data(self.data)
            self.refresh_project_list()
            self.select_project(new_proj["id"])
 
    def set_project_importance(self, project_id, value):
        for p in self.data["projects"]:
            if p["id"] == project_id:
                p["importance"] = value
        save_data(self.data)
        self.refresh_project_list()
        if project_id == self.selected_project_id:
            self.refresh_main_area()
 
    # ---------------- Main area ----------------
    def _build_main_area(self):
        self.main = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_rowconfigure(4, weight=1)
        self.main.grid_columnconfigure(0, weight=1)
 
        top_bar = ctk.CTkFrame(self.main, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=30, pady=(24, 4))
        top_bar.grid_columnconfigure(0, weight=1)
 
        self.project_title_label = ctk.CTkLabel(
            top_bar, text="Kein Projekt ausgewählt",
            font=ctk.CTkFont(size=26, weight="bold"), anchor="w"
        )
        self.project_title_label.grid(row=0, column=0, sticky="w")
 
        btns = ctk.CTkFrame(top_bar, fg_color="transparent")
        btns.grid(row=0, column=1, sticky="e")
 
        rename_btn = ctk.CTkButton(btns, text="✎ Umbenennen", width=120, command=self.rename_project)
        rename_btn.pack(side="left", padx=5)
 
        delete_btn = ctk.CTkButton(btns, text="🗑 Löschen", width=100, fg_color="#c0392b", hover_color="#922b21", command=self.delete_project)
        delete_btn.pack(side="left", padx=5)
 
        importance_row = ctk.CTkFrame(self.main, fg_color="transparent")
        importance_row.grid(row=1, column=0, sticky="w", padx=30, pady=(0, 10))
        ctk.CTkLabel(importance_row, text="Wichtigkeit des Projekts:", font=ctk.CTkFont(size=13), text_color="#aaaaaa").pack(side="left", padx=(0, 8))
        self.project_star_widget = StarRating(importance_row, value=3, size=20, editable=True, on_change=self._on_header_star_change)
        self.project_star_widget.pack(side="left")
 
        # Progress
        progress_frame = ctk.CTkFrame(self.main, fg_color="transparent")
        progress_frame.grid(row=2, column=0, sticky="ew", padx=30, pady=(0, 16))
        progress_frame.grid_columnconfigure(0, weight=1)
 
        self.progress_bar = ctk.CTkProgressBar(progress_frame, height=14)
        self.progress_bar.grid(row=0, column=0, sticky="ew")
        self.progress_bar.set(0)
 
        self.progress_label = ctk.CTkLabel(progress_frame, text="", font=ctk.CTkFont(size=13))
        self.progress_label.grid(row=0, column=1, padx=12)
 
        # Addon-Panel: Hier können Addons (z.B. Budget & Ressourcen) eigene Widgets einklinken.
        # Liegt bewusst IM progress_frame (statt eigener Grid-Zeile), damit sich bei leerem
        # Panel (kein Addon aktiv / kein Budget gesetzt) am Layout absolut nichts verschiebt.
        self.addon_panel_frame = ctk.CTkFrame(progress_frame, fg_color="transparent", width=1, height=1)
        self.addon_panel_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 0))
        self.addon_panel_frame.grid_columnconfigure(0, weight=1)
 
        # Add task bar
        add_frame = ctk.CTkFrame(self.main, fg_color="#262626", corner_radius=12)
        add_frame.grid(row=3, column=0, sticky="ew", padx=30, pady=(0, 16))
        add_frame.grid_columnconfigure(0, weight=1)
 
        self.new_task_entry = ctk.CTkEntry(add_frame, placeholder_text="Neue Aufgabe eingeben...", height=38)
        self.new_task_entry.grid(row=0, column=0, sticky="ew", padx=(12, 8), pady=12)
        self.new_task_entry.bind("<Return>", lambda e: self.add_task())
 
        ctk.CTkLabel(add_frame, text="Wichtigkeit:", font=ctk.CTkFont(size=12), text_color="#aaaaaa").grid(row=0, column=1, padx=(6, 4))
        self.new_task_stars = StarRating(add_frame, value=3, size=16, editable=True)
        self.new_task_stars.grid(row=0, column=2, padx=6, pady=12)
 
        self.due_entry = ctk.CTkEntry(add_frame, placeholder_text="Fällig (TT.MM.JJJJ)", width=150, height=38)
        self.due_entry.grid(row=0, column=3, padx=6, pady=12)
 
        add_btn = ctk.CTkButton(add_frame, text="+ Hinzufügen", height=38, command=self.add_task)
        add_btn.grid(row=0, column=4, padx=(6, 12), pady=12)
 
        # Task scroll list
        self.task_scroll = ctk.CTkScrollableFrame(self.main, fg_color="transparent")
        self.task_scroll.grid(row=4, column=0, sticky="nsew", padx=30, pady=(0, 24))
        self.task_scroll.grid_columnconfigure(0, weight=1)
 
    def _on_header_star_change(self, value):
        proj = self.get_selected_project()
        if proj:
            self.set_project_importance(proj["id"], value)
 
    def get_selected_project(self):
        for p in self.data["projects"]:
            if p["id"] == self.selected_project_id:
                return p
        return None
 
    def select_project(self, project_id):
        self.selected_project_id = project_id
        self.refresh_project_list()
        self.refresh_main_area()
 
    def refresh_main_area(self):
        proj = self.get_selected_project()
        for w in self.task_scroll.winfo_children():
            w.destroy()
        for w in self.addon_panel_frame.winfo_children():
            w.destroy()
 
        if not proj:
            self.project_title_label.configure(text="Kein Projekt ausgewählt")
            self.project_star_widget.set_value(0)
            self.progress_bar.set(0)
            self.progress_label.configure(text="")
            return
 
        self.project_title_label.configure(text=proj["name"])
        self.project_star_widget.set_value(proj.get("importance", 3))
 
        # Von Addons registrierte Panels einblenden (z.B. Budget & Ressourcen)
        for render_func in self.project_panel_hooks:
            try:
                render_func(self.addon_panel_frame, proj)
            except Exception as e:
                print(f"[Addon-Panel-Fehler] {e}")
 
        tasks = proj["tasks"]
        total = len(tasks)
        done = sum(1 for t in tasks if t.get("done"))
        pct = (done / total) if total else 0
        self.progress_bar.set(pct)
        self.progress_label.configure(text=f"{done}/{total} erledigt ({int(pct*100)}%)")
 
        # Sortierung: offene Aufgaben zuerst, dann nach Wichtigkeit (Sterne) absteigend
        sorted_tasks = sorted(
            tasks,
            key=lambda t: (t.get("done", False), -t.get("importance", 3))
        )
 
        if not tasks:
            empty_label = ctk.CTkLabel(self.task_scroll, text="Noch keine Aufgaben – füge oben eine hinzu ✨", text_color="#888888")
            empty_label.pack(pady=40)
            return
 
        for task in sorted_tasks:
            row = TaskRow(
                self.task_scroll, task,
                on_toggle=self.toggle_task,
                on_delete=self.delete_task,
                on_importance_change=self.set_task_importance,
                on_open_attachments=self.open_attachments_dialog,
            )
            row.pack(fill="x", pady=5)
 
    def add_task(self):
        proj = self.get_selected_project()
        if not proj:
            messagebox.showinfo(APP_NAME, "Bitte wähle zuerst ein Projekt aus oder erstelle eines.")
            return
        title = self.new_task_entry.get().strip()
        if not title:
            return
        due = self.due_entry.get().strip()
        if due:
            try:
                datetime.strptime(due, "%d.%m.%Y")
            except ValueError:
                messagebox.showwarning(APP_NAME, "Datum bitte im Format TT.MM.JJJJ eingeben.")
                return
 
        task = {
            "id": str(uuid.uuid4()),
            "title": title,
            "done": False,
            "importance": self.new_task_stars.value,
            "due": due,
            "attachments": [],
            "notes": "",
        }
        proj["tasks"].append(task)
        save_data(self.data)
        self.new_task_entry.delete(0, "end")
        self.due_entry.delete(0, "end")
        self.new_task_stars.set_value(3)
        self.refresh_project_list()
        self.refresh_main_area()
 
    def toggle_task(self, task_id, value):
        proj = self.get_selected_project()
        if not proj:
            return
        for t in proj["tasks"]:
            if t["id"] == task_id:
                t["done"] = value
        save_data(self.data)
        self.refresh_project_list()
        self.refresh_main_area()
 
    def set_task_importance(self, task_id, value):
        proj = self.get_selected_project()
        if not proj:
            return
        for t in proj["tasks"]:
            if t["id"] == task_id:
                t["importance"] = value
        save_data(self.data)
        # Nur die Liste neu sortieren/aufbauen, Sidebar unverändert
        self.refresh_main_area()
 
    def delete_task(self, task_id):
        proj = self.get_selected_project()
        if not proj:
            return
        proj["tasks"] = [t for t in proj["tasks"] if t["id"] != task_id]
        save_data(self.data)
        self.refresh_project_list()
        self.refresh_main_area()
 
    def rename_project(self):
        proj = self.get_selected_project()
        if not proj:
            return
        dialog = ctk.CTkInputDialog(text="Neuer Projektname:", title="Umbenennen")
        name = dialog.get_input()
        if name:
            proj["name"] = name
            save_data(self.data)
            self.refresh_project_list()
            self.refresh_main_area()
 
    def delete_project(self):
        proj = self.get_selected_project()
        if not proj:
            return
        if messagebox.askyesno(APP_NAME, f"Projekt '{proj['name']}' wirklich löschen?"):
            self.data["projects"] = [p for p in self.data["projects"] if p["id"] != proj["id"]]
            save_data(self.data)
            remaining = self._sorted_projects()
            self.selected_project_id = remaining[0]["id"] if remaining else None
            self.refresh_project_list()
            self.refresh_main_area()
 
    # ---------------- Details: Notizen, Dateien & Links ----------------
    def open_attachments_dialog(self, task_id):
        proj = self.get_selected_project()
        if not proj:
            return
        task = next((t for t in proj["tasks"] if t["id"] == task_id), None)
        if task is None:
            return
 
        win = ctk.CTkToplevel(self)
        win.title(f"Details – {task['title']}")
        win.geometry("560x640")
        win.transient(self)
        win.grab_set()
 
        ctk.CTkLabel(win, text=f"📝 Details für: {task['title']}", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(16, 8), padx=16, anchor="w")
 
        # --- Notizen ---
        ctk.CTkLabel(win, text="Notizen / Details", font=ctk.CTkFont(size=13, weight="bold"), text_color="#cccccc").pack(padx=16, anchor="w")
        notes_box = ctk.CTkTextbox(win, height=110)
        notes_box.pack(fill="x", padx=16, pady=(4, 4))
        notes_box.insert("1.0", task.get("notes", ""))
 
        def save_notes():
            task["notes"] = notes_box.get("1.0", "end-1c")
            save_data(self.data)
            self.refresh_main_area()
 
        ctk.CTkButton(win, text="💾 Notizen speichern", height=30, command=save_notes).pack(padx=16, anchor="e", pady=(0, 12))
 
        # --- Anhänge (Dateien & Links) ---
        ctk.CTkLabel(win, text="Anhänge (Dateien & Links)", font=ctk.CTkFont(size=13, weight="bold"), text_color="#cccccc").pack(padx=16, anchor="w")
 
        list_frame = ctk.CTkScrollableFrame(win, fg_color="transparent", height=220)
        list_frame.pack(fill="both", expand=True, padx=16, pady=8)
 
        def render_list():
            for w in list_frame.winfo_children():
                w.destroy()
            attachments = task.get("attachments", [])
            if not attachments:
                ctk.CTkLabel(list_frame, text="Noch keine Datei oder kein Link angehängt.", text_color="#888888").pack(pady=20)
                return
            for att in attachments:
                row = ctk.CTkFrame(list_frame, fg_color="#242424", corner_radius=8)
                row.pack(fill="x", pady=4)
 
                is_link = att.get("type") == "link"
                icon = "🔗" if is_link else "📄"
                exists = True if is_link else os.path.exists(att["target"])
                name_color = "#ffffff" if exists else "#e74c3c"
                label_text = f"{icon} {att['name']}" + ("" if exists else "  (nicht gefunden)")
 
                ctk.CTkLabel(row, text=label_text, text_color=name_color, anchor="w").pack(side="left", padx=10, pady=8, fill="x", expand=True)
                ctk.CTkButton(row, text="Öffnen", width=70, command=lambda a=att: open_attachment(a)).pack(side="left", padx=4)
                ctk.CTkButton(
                    row, text="Entfernen", width=80, fg_color="#c0392b", hover_color="#922b21",
                    command=lambda a=att: remove_attachment(a)
                ).pack(side="left", padx=(4, 10))
 
        def remove_attachment(att):
            task["attachments"] = [a for a in task["attachments"] if a is not att]
            save_data(self.data)
            render_list()
            self.refresh_main_area()
 
        def add_via_dialog():
            path = filedialog.askopenfilename(title="Datei auswählen")
            if path:
                task.setdefault("attachments", []).append({
                    "type": "file", "target": path, "name": os.path.basename(path)
                })
                save_data(self.data)
                render_list()
                self.refresh_main_area()
 
        def add_via_manual_path():
            path = simpledialog.askstring(
                "Pfad eingeben",
                "Vollständigen Datei- oder Ordnerpfad eingeben\n(z.B. für Netzlaufwerke: \\\\server\\freigabe\\datei.pdf):",
                parent=win
            )
            if path:
                task.setdefault("attachments", []).append({
                    "type": "file", "target": path,
                    "name": os.path.basename(path.rstrip("\\/")) or path
                })
                save_data(self.data)
                render_list()
                self.refresh_main_area()
 
        def add_link():
            url = simpledialog.askstring(
                "Link hinzufügen", "Website-URL eingeben (z.B. https://beispiel.de):", parent=win
            )
            if not url:
                return
            if not (url.startswith("http://") or url.startswith("https://")):
                url = "https://" + url
            display_name = simpledialog.askstring(
                "Linkname", "Kurzer Name für den Link (optional):", parent=win
            ) or url
            task.setdefault("attachments", []).append({"type": "link", "target": url, "name": display_name})
            save_data(self.data)
            render_list()
            self.refresh_main_area()
 
        button_row = ctk.CTkFrame(win, fg_color="transparent")
        button_row.pack(fill="x", padx=16, pady=(4, 16))
        ctk.CTkButton(button_row, text="📁 Datei", width=90, command=add_via_dialog).pack(side="left", padx=(0, 6))
        ctk.CTkButton(button_row, text="🔗 Link", width=90, command=add_link).pack(side="left", padx=(0, 6))
        ctk.CTkButton(button_row, text="✎ Pfad manuell", fg_color="#333333", hover_color="#444444", command=add_via_manual_path).pack(side="left")
 
        render_list()
 
    # ---------------- Addon-Center ----------------
    def reload_addons(self):
        self.addon_api = AddonAPI(self)
        self.addon_results = load_addons(self.addon_api)
 
    def open_addon_center(self):
        win = ctk.CTkToplevel(self)
        win.title("🧩 Addon-Center")
        win.geometry("560x520")
        win.transient(self)
        win.grab_set()
 
        ctk.CTkLabel(win, text="🧩 Addon-Center", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(16, 4), padx=16, anchor="w")
        ctk.CTkLabel(
            win, text=f"Addon-Ordner: {ADDONS_DIR}",
            text_color="#888888", font=ctk.CTkFont(size=11), wraplength=520, justify="left"
        ).pack(padx=16, anchor="w")
 
        top_buttons = ctk.CTkFrame(win, fg_color="transparent")
        top_buttons.pack(fill="x", padx=16, pady=12)
 
        def refresh_window():
            for w in content.winfo_children():
                w.destroy()
            build_content(content)
 
        def do_reload():
            self.reload_addons()
            refresh_window()
 
        ctk.CTkButton(top_buttons, text="📂 Addon-Ordner öffnen", command=lambda: open_path(ADDONS_DIR)).pack(side="left", padx=(0, 8))
        ctk.CTkButton(top_buttons, text="🔄 Addons neu laden", command=do_reload).pack(side="left", padx=(0, 8))
 
        def create_example():
            example_path = os.path.join(ADDONS_DIR, "beispiel_addon.py")
            if os.path.exists(example_path):
                if not messagebox.askyesno(APP_NAME, "beispiel_addon.py existiert schon. Überschreiben?"):
                    return
            with open(example_path, "w", encoding="utf-8") as f:
                f.write(EXAMPLE_ADDON_CODE)
            messagebox.showinfo(APP_NAME, "Beispiel-Addon wurde erstellt!\nKlicke auf 'Addons neu laden'.")
            refresh_window()
 
        ctk.CTkButton(top_buttons, text="✨ Beispiel-Addon erstellen", fg_color="#333333", hover_color="#444444", command=create_example).pack(side="left")
 
        content = ctk.CTkScrollableFrame(win, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=(0, 16))
 
        def run_action(action):
            try:
                action["callback"](self.addon_api)
            except Exception as e:
                messagebox.showerror(APP_NAME, f"Fehler im Addon '{action['label']}':\n{e}")
 
        def build_content(parent):
            ctk.CTkLabel(parent, text="Geladene Addons", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(4, 4))
            if not self.addon_results:
                ctk.CTkLabel(parent, text="Keine Addons gefunden. Lege .py-Dateien in den Addon-Ordner.", text_color="#888888").pack(anchor="w", pady=(0, 12))
            for r in self.addon_results:
                icon = {"ok": "✅", "warn": "⚠️", "error": "❌"}.get(r["status"], "•")
                row = ctk.CTkFrame(parent, fg_color="#242424", corner_radius=8)
                row.pack(fill="x", pady=3)
                text = f"{icon} {r['name']}.py"
                ctk.CTkLabel(row, text=text, anchor="w").pack(anchor="w", padx=10, pady=(8, 0))
                if r["error"]:
                    ctk.CTkLabel(row, text=r["error"], text_color="#e74c3c", font=ctk.CTkFont(size=11), wraplength=480, justify="left", anchor="w").pack(anchor="w", padx=10, pady=(0, 8))
                else:
                    ctk.CTkFrame(row, fg_color="transparent", height=4).pack()
 
            ctk.CTkLabel(parent, text="Addon-Aktionen", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(16, 4))
            if not self.addon_api.actions:
                ctk.CTkLabel(parent, text="Keine Aktionen registriert.", text_color="#888888").pack(anchor="w")
            for action in self.addon_api.actions:
                ctk.CTkButton(
                    parent, text=f"{action['icon']} {action['label']}", anchor="w",
                    command=lambda a=action: run_action(a)
                ).pack(fill="x", pady=3)
 
        build_content(content)
 
 
if __name__ == "__main__":
    app = ProjectPlannerApp()
    app.mainloop()
 