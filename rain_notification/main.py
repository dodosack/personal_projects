import requests
import os
import sys
import time
from dotenv import load_dotenv

# --- 1. Konfiguration & Secrets laden ---
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
LOCATION = os.getenv("Q")


# --- 2. Telegram Sende-Funktion (Robust, mit MarkdownV2) ---
def send_telegram_message(message_text, retries=3, delay=1):
    """
    Sendet eine Nachricht über den Telegram Bot mit robustem Error-Handling.
    Nutzt MarkdownV2.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message_text,
        "parse_mode": "MarkdownV2"  # <-- Zurückgeändert
    }

    for attempt in range(retries):
        try:
            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                print("✓ Telegram-Nachricht erfolgreich gesendet")
                return True

            print(f"✗ Telegram-API-Fehler (Status {response.status_code}):")
            try:
                error_data = response.json()
                description = error_data.get('description', 'Keine Beschreibung')
                print(f"  Beschreibung: {description}")

                if response.status_code == 429:
                    retry_after = error_data.get('parameters', {}).get('retry_after', delay)
                    print(f"  Rate Limit erreicht. Warte {retry_after} Sekunden...")
                    time.sleep(retry_after)
                    delay *= 2
                elif 400 <= response.status_code < 500:
                    # Spezieller Check für Markdown-Fehler
                    if 'parse error' in description.lower():
                        print("  -> FEHLER: MarkdownV2 Formatierungsfehler. Prüfe auf nicht-escapete Sonderzeichen.")
                    else:
                        print("  Client-Fehler (z.B. Chat-ID falsch?). Breche Senden ab.")
                    return False
            except requests.exceptions.JSONDecodeError:
                print(f"  Konnte Fehler-Antwort nicht als JSON parsen: {response.text}")

        except requests.exceptions.RequestException as e:
            print(f"✗ Netzwerk-Fehler beim Senden an Telegram: {e}")

        if attempt < retries - 1:
            print(f"  Versuche erneut in {delay}s...")
            time.sleep(delay)

    print(f"✗ Nachricht konnte nach {retries} Versuchen nicht gesendet werden.")
    return False


# --- 3. Wetter-Abhol-Funktion ---
# (Diese Funktion bleibt exakt gleich wie in deinem Code)
def get_weather_forecast(location):
    """
    Fragt die WeatherAPI nach der Vorhersage für einen Ort ab.
    Gibt die JSON-Antwort als Python-Dictionary zurück.
    """
    base_url = "https://api.weatherapi.com/v1/forecast.json"
    params = {
        'key': WEATHER_API_KEY,
        'q': location,
        'days': 1,
        'lang': 'de'
    }
    headers = {
        'accept': 'application/json'
    }

    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as http_err:
        print(f"✗ HTTP-Fehler bei WeatherAPI: {http_err}")
        if http_err.response.status_code == 401:
            print("  -> FEHLER: Dein WEATHER_API_KEY ist ungültig oder abgelaufen.")
        elif http_err.response.status_code == 400:
            print(f"  -> FEHLER: Ort '{location}' nicht gefunden (400 Bad Request).")
        print(f"  Antwort-Text: {http_err.response.text}")
    except requests.exceptions.RequestException as req_err:
        print(f"✗ Netzwerk-Fehler bei WeatherAPI: {req_err}")

    return None


# --- 4. HAUPT-LOGIK ---
if __name__ == "__main__":
    print("Starte Wetter-Bot...")

    if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, WEATHER_API_KEY, LOCATION]):
        print("FEHLER: Eine der Umgebungsvariablen (.env) fehlt!")
        print("Stelle sicher, dass TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, WEATHER_API_KEY und Q gesetzt sind.")
        sys.exit(1)

    print(f"Prüfe Wetter für Standort: {LOCATION}...")
    weather_data = get_weather_forecast(LOCATION)

    if weather_data:
        try:
            forecast_day = weather_data['forecast']['forecastday'][0]['day']
            will_it_rain = forecast_day['daily_will_it_rain']
            chance = forecast_day['daily_chance_of_rain']
            condition_text = forecast_day['condition']['text']  # z.B. "Starkregen"
            max_temp = forecast_day['maxtemp_c']
            min_temp = forecast_day['mintemp_c']

            if will_it_rain == 1:
                print(f"✓ Regen für {LOCATION} gemeldet (Chance: {chance}%)")

                # WICHTIG: Sonderzeichen für MarkdownV2 escapen
                # Telegram ist hier sehr streng. Wir escapen die häufigsten Problemzeichen.
                special_chars = r"_*[]()~`>#+-=|{}.!"
                escaped_location = LOCATION
                escaped_condition = condition_text
                for char in special_chars:
                    escaped_location = escaped_location.replace(char, f"\\{char}")
                    escaped_condition = escaped_condition.replace(char, f"\\{char}")

                message = (
                    f"☔️ *Regen\\-Alarm für {escaped_location}*\n\n"
                    f"*Vorhersage:* {escaped_condition}\n"
                    f"*Chance:* {chance}%\n"
                    f"*Temp:* {min_temp}°C bis {max_temp}°C"
                )

                send_telegram_message(message)
            else:
                print(f"✓ Kein Regen für {LOCATION} gemeldet. Sende nichts.")

        except (KeyError, IndexError, TypeError) as e:
            print(f"✗ Fehler beim Parsen der JSON-Antwort: {e}")
            send_telegram_message(f"🚨 Bot\\-Fehler: Konnte Wetter\\-JSON nicht parsen: {e}")
    else:
        print("✗ Wetterabruf fehlgeschlagen. Es wird keine Nachricht gesendet.")
        send_telegram_message(f"🚨 Bot\\-Fehler: Wetter\\-API\\-Abruf für {LOCATION} ist fehlgeschlagen\\.")

    print("Wetter-Bot beendet.")