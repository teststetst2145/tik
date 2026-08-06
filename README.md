# TikTok Celebrity Tracker – Anleitung

---

## 🖥️ Teil 1: Lokal testen (5 Minuten)

### Schritt 1 – Python prüfen
Öffne die Eingabeaufforderung (Windows-Taste → `cmd` eintippen):
```
python --version
```
→ Muss `Python 3.10` oder höher zeigen. Falls nicht: https://python.org/downloads

### Schritt 2 – Pakete installieren
```
pip install yt-dlp rich schedule
```

### Schritt 3 – Tool starten
In den Ordner wechseln wo `tracker.py` liegt:
```
cd "C:\Users\Lills\Desktop\Neuer Ordner\vibe coded checker"
```

Dann starten (Username anpassen!):
```
python tracker.py charlidamelio
```

Das Tool:
- prüft neue Videos & Reposts
- sucht aktive Stories und lädt sie herunter
- speichert alles in `data/`

### Weitere Befehle:
```bash
# Alle 15 Minuten automatisch prüfen (läuft so lange das Fenster offen ist)
python tracker.py charlidamelio --watch 15

# Verlauf der letzten Events anzeigen
python tracker.py charlidamelio --history

# Zusammenfassung anzeigen
python tracker.py charlidamelio --stats

# Nur Videos, keine Stories (schneller)
python tracker.py charlidamelio --no-stories
```

---

## ☁️ Teil 2: Dauerhaft auf GitHub (läuft auch wenn PC aus ist)

### Schritt 1 – GitHub Account
Falls noch keiner: https://github.com/signup (kostenlos)

### Schritt 2 – Neues Repository erstellen
1. https://github.com/new aufrufen
2. Name z.B. `tiktok-tracker`
3. **Public** lassen (für kostenlose GitHub Pages)
4. Auf **"Create repository"** klicken

### Schritt 3 – Dateien hochladen
Im neuen Repo auf **"uploading an existing file"** klicken und diese Dateien hochladen:

```
tracker.py
build_dashboard.py
requirements.txt
```

Dann den Ordner `.github/workflows/` mit der Datei `tracker.yml` hochladen:
- Oben im Repo auf **"Add file" → "Create new file"** klicken
- Als Dateiname eingeben: `.github/workflows/tracker.yml`
- Den Inhalt aus der lokalen `tracker.yml` reinkopieren
- Auf **"Commit changes"** klicken

### Schritt 4 – TikTok Username als Variable speichern
1. Im Repo auf **Settings** (oben)
2. Links: **Secrets and variables → Actions**
3. Tab **Variables** → **"New repository variable"**
4. Name: `TIKTOK_USERNAME`
5. Value: z.B. `charlidamelio` (ohne @)
6. **"Add variable"** klicken

### Schritt 5 – GitHub Pages aktivieren
1. Im Repo auf **Settings**
2. Links: **Pages**
3. Bei **Source**: `GitHub Actions` auswählen
4. Speichern

### Schritt 6 – Ersten Lauf starten
1. Im Repo auf **Actions** (oben)
2. Links: **TikTok Tracker** anklicken
3. Rechts: **"Run workflow"** → **"Run workflow"** klicken
4. ~2 Minuten warten

→ Dashboard ist danach live unter:
```
https://DEIN-GITHUBNAME.github.io/tiktok-tracker/
```

Ab jetzt läuft es **automatisch alle 30 Minuten** – kostenlos, auch wenn dein PC aus ist.

---

## ❓ Funktioniert nicht? (häufige Probleme)

### Problem: "No entries returned"
TikTok blockiert den Zugriff ohne Login.

**Lösung – Cookies exportieren:**
1. Im Chrome/Firefox die Extension **"Get cookies.txt LOCALLY"** installieren
2. Auf tiktok.com einloggen
3. Extension öffnen → **Export** → Datei als `cookies.txt` speichern
4. `cookies.txt` in denselben Ordner wie `tracker.py` legen
5. In `tracker.py` in der Funktion `_run_ytdlp` diese Zeile ergänzen:
   ```python
   cmd = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--cookies", "cookies.txt"] + args
   ```
6. Für GitHub: `cookies.txt` als **Secret** speichern (Settings → Secrets → Actions → New secret, Name: `TIKTOK_COOKIES`) und im Workflow mit `echo "${{ secrets.TIKTOK_COOKIES }}" > cookies.txt` wiederherstellen

### Problem: Stories werden nicht gefunden
Stories sind oft nur mit Login sichtbar → ebenfalls Cookies-Lösung (s.o.)

### Problem: Python nicht gefunden
- Beim Python-Installer **"Add Python to PATH"** aktivieren
- Dann neu installieren

---

## 📁 Wo sind meine Daten?

```
data/
  charlidamelio.json          ← alle Videos + Metadaten
  charlidamelio_log.jsonl     ← chronologischer Event-Log
  charlidamelio/
    stories/
      12345.mp4               ← heruntergeladene Story-Videos
docs/
  index.html                  ← Dashboard (GitHub Pages)
```
