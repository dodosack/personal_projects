
import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import time

import os
from dotenv import load_dotenv

# Dieser Befehl lädt die Variablen aus deiner .env-Datei
load_dotenv()




# ==================== KONFIGURATION ====================
#MOODLE_URL = "https://deine-hochschule.moodle.de/course/view.php?id=KURS_ID"
COOKIES_FILE = "cookies.json"  # Exportierte Cookies aus dem Browser

MOODLE_URL = os.getenv("MOODLE_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DATA_FILE = "moodle_gruppen.json"
CHECK_INTERVAL = 20  # Prüfintervall in Sekunden s


# =======================================================


def is_logged_in(response):
    """Prüft ob Session noch gültig ist"""
    return "login" not in response.url.lower() and \
           "anmelden" not in response.text.lower()

def load_cookies():
    """Lädt Cookies aus JSON-Datei"""
    try:
        with open(COOKIES_FILE, 'r', encoding='utf-8') as f:
            cookies_list = json.load(f)

        # Konvertiere Liste zu Dictionary für requests
        cookies_dict = {}
        for cookie in cookies_list:
            # Unterstützt verschiedene Cookie-Exportformate
            if isinstance(cookie, dict):
                name = cookie.get('name') or cookie.get('Name')
                value = cookie.get('value') or cookie.get('Value')
                if name and value:
                    cookies_dict[name] = value

        print(f"✓ {len(cookies_dict)} Cookies geladen")
        return cookies_dict
    except FileNotFoundError:
        print(f"✗ Cookies-Datei nicht gefunden: {COOKIES_FILE}")
        print("   Exportiere deine Browser-Cookies als JSON und speichere sie als 'cookies.json'")
        return None
    except Exception as e:
        print(f"✗ Fehler beim Laden der Cookies: {e}")
        return None


def send_telegram_message(message):
    """Sendet eine Nachricht über Telegram Bot"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("✓ Telegram-Nachricht gesendet")
        else:
            print(f"✗ Fehler beim Senden: {response.status_code}")
    except Exception as e:
        print(f"✗ Telegram-Fehler: {e}")


def fetch_moodle_groups():
    """Ruft Gruppendaten von Moodle ab"""


    cookies = load_cookies()
    if not cookies:
        return None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        response = requests.get(MOODLE_URL, headers=headers, cookies=cookies, timeout=10)
        response.raise_for_status()

        # <-- Hier Session-Prüfung einfügen
        if not is_logged_in(response):
            send_telegram_message("⚠️ Cookies abgelaufen - bitte erneuern!")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        groups = {}

        # Finde alle Tabellenzeilen (tr)
        table_rows = soup.find_all('tr')

        for row in table_rows:
            # Suche nach der Zelle mit dem Gruppennamen
            # Der Gruppenname steht in einer td, die "Group XX" enthält
            cells = row.find_all('td')

            group_name = None
            capacity = None

            for i, cell in enumerate(cells):
                cell_text = cell.get_text(strip=True)

                # Finde Gruppennamen (beginnt mit "Group")
                if cell_text.startswith('Group'):
                    group_name = cell_text

                # Finde Kapazität (Format "X / Y")
                if '/' in cell_text and cell_text.replace('/', '').replace(' ', '').isdigit():
                    capacity = cell_text

            # Wenn beide gefunden wurden, speichern
            if group_name and capacity:
                groups[group_name] = capacity

        # Alternative Methode falls keine Gruppen gefunden
        if not groups:
            # Suche direkt nach Text-Pattern "Group XX"
            for td in soup.find_all('td'):
                text = td.get_text(strip=True)
                if text.startswith('Group'):
                    # Finde die nächste td mit Kapazität
                    next_tds = td.find_next_siblings('td')
                    for next_td in next_tds:
                        capacity_text = next_td.get_text(strip=True)
                        if '/' in capacity_text:
                            groups[text] = capacity_text
                            break

        print(f"✓ {len(groups)} Gruppen gefunden")
        return groups

    except requests.exceptions.RequestException as e:
        print(f"✗ Fehler beim Abrufen: {e}")
        return None


def load_previous_data():
    """Lädt gespeicherte Gruppendaten"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"✗ Fehler beim Laden: {e}")
    return {}


def save_data(data):
    """Speichert Gruppendaten"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✓ Daten gespeichert: {DATA_FILE}")
    except Exception as e:
        print(f"✗ Fehler beim Speichern: {e}")


def compare_and_notify(old_data, new_data):
    """Vergleicht Daten und sendet Benachrichtigungen"""
    if not new_data:
        return

    changes = []

    # Neue Gruppen
    for group, size in new_data.items():
        if group not in old_data:
            changes.append(f"➕ <b>Neue Gruppe:</b> {group} ({size} Mitglieder)")
        elif old_data[group] != size:
            changes.append(f"📊 <b>Größe geändert:</b> {group}\n   {old_data[group]} → {size}")

    # Gelöschte Gruppen
    for group in old_data:
        if group not in new_data:
            changes.append(f"➖ <b>Gruppe entfernt:</b> {group}")

    if changes:
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
        message = f"🔔 <b>Moodle Gruppenänderungen</b>\n{timestamp}\n\n"
        message += "\n\n".join(changes)
        send_telegram_message(message)
        print(f"✓ {len(changes)} Änderung(en) erkannt")
    else:
        print("○ Keine Änderungen")


def main():
    """Hauptfunktion"""
    print("=== Moodle Gruppen Monitor gestartet ===")
    print(f"Prüfintervall: {CHECK_INTERVAL}s\n")

    # Erste Prüfung
    old_data = load_previous_data()
    new_data = fetch_moodle_groups()

    if new_data:
        if not old_data:
            # Erstmalige Ausführung
            save_data(new_data)
            send_telegram_message(f"✅ Moodle Monitor gestartet\n{len(new_data)} Gruppen werden überwacht")
        else:
            compare_and_notify(old_data, new_data)
            save_data(new_data)

    # Kontinuierliche Überwachung
    try:
        while True:
            print(f"\n⏳ Warte {CHECK_INTERVAL}s...")
            time.sleep(CHECK_INTERVAL)

            old_data = load_previous_data()
            new_data = fetch_moodle_groups()

            if new_data:
                compare_and_notify(old_data, new_data)
                save_data(new_data)

    except KeyboardInterrupt:
        print("\n\n=== Monitor gestoppt ===")


if __name__ == "__main__":
    main()