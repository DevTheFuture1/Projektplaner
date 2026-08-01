# Projektplaner – Desktop App

Eine einfache, hübsche Desktop-App zur Projekt- und Aufgabenplanung. Läuft komplett
lokal auf deinem PC, speichert alle Daten dauerhaft in einer Datei auf deinem Rechner
(kein Internet, kein Cloud-Zwang).

## Was du bekommst
- `app.py` – der komplette Programmcode
- `requirements.txt` – die zwei benötigten Pakete
- `build_exe.bat` – baut dir automatisch eine eigenständige `Projektplaner.exe`
- Diese Anleitung

## So machst du daraus eine echte Windows-.exe (einmalig, ca. 2 Minuten)

**Voraussetzung:** Python 3.10+ ist installiert. Falls nicht:
Lade es von https://www.python.org/downloads/ herunter und installiere es
(bei der Installation unbedingt **"Add Python to PATH"** anhaken).

**Schritte:**
1. Entpacke alle Dateien in einen Ordner, z.B. `C:\Projektplaner`
2. Doppelklick auf `build_exe.bat`
3. Warten, bis "Fertig!" erscheint
4. Die fertige App liegt danach unter: `dist\Projektplaner.exe`
5. Diese `.exe` kannst du verschieben, ein Desktop-Verknüpfung dafür anlegen,
   oder sie einfach direkt per Doppelklick starten — **kein Python nötig, nichts
   weiter zu installieren.**

Tipp: Rechtsklick auf `Projektplaner.exe` → "Verknüpfung erstellen" → die
Verknüpfung auf den Desktop ziehen, damit du sie wie jede andere Windows-App
starten kannst.

## Was die App kann
- Beliebig viele Projekte anlegen, umbenennen, löschen
- Aufgaben pro Projekt hinzufügen mit Fälligkeitsdatum
- Aufgaben abhaken, löschen
- Fortschrittsbalken pro Projekt (X von Y erledigt in %)
- **⭐ Sterne-Bewertung (1-5)** für Projekte UND Aufgaben – einfach auf die Sterne klicken.
  Projekte lassen sich in der Seitenleiste nach Wichtigkeit oder Name sortieren.
- **📎 Details pro Aufgabe** – zu jeder Aufgabe kannst du:
  - **Notizen** schreiben (Freitext für zusätzliche Infos, z.B. Ansprechpartner, Kontext, ToDo-Details)
  - **Dateien** anhängen (Bilder, PDFs, Dokumente) über Auswahldialog oder manuellen Pfad (z.B. Netzlaufwerke)
  - **Website-Links** anhängen (öffnen sich direkt im Standard-Browser)
  Alles erreichbar über den Button rechts neben jeder Aufgabe (zeigt an, was vorhanden ist: 📄 Dateien, 🔗 Links, 📝 Notizen)
- **🧩 Addon-System** – eigene Python-Erweiterungen einbinden (siehe unten)
- Dunkles, modernes UI-Design

## 🧩 Addon-System – eigene Erweiterungen schreiben

Die App hat einen Ordner für Addons:
`%APPDATA%\Projektplaner\addons\`

Du erreichst ihn am einfachsten über den Button **"🧩 Addons"** unten links in der App
→ "📂 Addon-Ordner öffnen". Dort kannst du dir auch per Klick auf
**"✨ Beispiel-Addon erstellen"** eine fertige Beispieldatei erzeugen lassen, die du
als Vorlage nehmen kannst.

Ein Addon ist einfach eine `.py`-Datei in diesem Ordner mit einer Funktion `register(api)`:

```python
def register(api):
    api.add_action("Mein Button-Text", meine_funktion, icon="🚀")

def meine_funktion(api):
    proj = api.get_selected_project()
    api.show_info("Hallo", f"Aktuelles Projekt: {proj['name']}")
```

Nach dem Speichern der Datei einfach im Addon-Center auf **"🔄 Addons neu laden"** klicken –
dein Button erscheint dann im Addon-Center unter "Addon-Aktionen".

**Was ein Addon über `api` machen darf:**
| Methode | Zweck |
|---|---|
| `api.add_action(label, callback, icon)` | Registriert einen Button im Addon-Center |
| `api.get_projects()` | Liste aller Projekte |
| `api.get_selected_project()` | Aktuell ausgewähltes Projekt (oder `None`) |
| `api.get_data()` | Alle Rohdaten (Projekte + Aufgaben) |
| `api.save()` | Speichert Änderungen dauerhaft ab |
| `api.refresh()` | Aktualisiert die Ansicht in der App |
| `api.show_info(titel, text)` / `api.show_warning(...)` | Zeigt ein Hinweisfenster |
| `api.ask_string(titel, frage)` | Fragt den Nutzer nach Text |
| `api.ask_open_file(titel)` | Öffnet einen Datei-Auswahldialog |
| `api.ask_save_file(titel)` | Öffnet einen "Speichern unter"-Dialog |

Wenn ein Addon einen Fehler wirft, stürzt die App **nicht** ab – der Fehler wird im
Addon-Center rot angezeigt (❌), damit du ihn beheben kannst.

## Wo werden meine Daten gespeichert?
Automatisch unter:
`%APPDATA%\Projektplaner\data.json`
(also z.B. `C:\Users\DeinName\AppData\Roaming\Projektplaner\data.json`)

Die Datei bleibt erhalten, auch wenn du die App neu baust oder aktualisierst.
Ein Backup ist so einfach wie diese eine Datei zu kopieren.

## Die App später anpassen
Öffne `app.py` in einem beliebigen Editor (z.B. VS Code oder Notepad++),
ändere was du willst, und führe `build_exe.bat` erneut aus, um eine neue
.exe zu erzeugen.
