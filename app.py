import os
import json
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, redirect, session
from flask_socketio import SocketIO
import requests
from bs4 import BeautifulSoup

# Optional desktop features (only work locally)
try:
    from plyer import notification
    import pygame
    pygame.mixer.init()
    def play_alert_sound():
        pygame.mixer.music.load("correct-beep.wav")
        pygame.mixer.music.play()
except Exception:
    def play_alert_sound():
        pass

app = Flask(__name__)
app.secret_key = 'grow-garden-secret-key'
socketio = SocketIO(app)

CONFIG_PATH = "config.json"

# Load or initialize config
def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    else:
        return {"Webhook": ""}

def save_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

config = load_config()

# Live data holders
stock = {}
weather = {"active": False, "event": ""}

# Parse stock & weather from the site
def fetch_stock():
    try:
        res = requests.get("https://gagstock.gleeze.com/grow-a-garden")
        soup = BeautifulSoup(res.text, "html.parser")
        items = {}
        for li in soup.select("ul")[0].find_all("li"):
            name, qty = li.text.rsplit(" – ", 1)
            items[name.strip()] = qty.strip()
        return {"SEEDS STOCK": items}
    except Exception as e:
        print("[Stock Fetch Error]", e)
        return stock

def fetch_weather():
    try:
        res = requests.get("https://gagstock.gleeze.com/grow-a-garden")
        if "Weather:" in res.text:
            soup = BeautifulSoup(res.text, "html.parser")
            text = soup.get_text()
            weather_line = [line for line in text.splitlines() if "Weather:" in line]
            if weather_line:
                event = weather_line[0].split("Weather:")[1].strip()
                return {"active": True, "event": event}
        return {"active": False, "event": ""}
    except Exception as e:
        print("[Weather Fetch Error]", e)
        return weather

# Monitor for changes
def monitor_changes():
    global stock, weather
    last_stock = {}
    last_weather = {}

    while True:
        try:
            new_stock = fetch_stock()
            new_weather = fetch_weather()

            if new_stock != last_stock:
                for item, qty in new_stock.get("SEEDS STOCK", {}).items():
                    old_qty = last_stock.get("SEEDS STOCK", {}).get(item)
                    if old_qty and qty != old_qty:
                        msg = f"🌱 {item} restocked! Now {qty}"
                        send_discord_alert(msg)
                        play_alert_sound()
                stock = new_stock
                last_stock = new_stock
                socketio.emit("stock_update", stock)

            if new_weather != last_weather:
                weather = new_weather
                last_weather = new_weather
                if weather["active"]:
                    send_discord_alert(f"⛈️ Weather Alert: {weather['event']}")
                    notification.notify(
                        title="Weather Alert",
                        message=weather['event'],
                        timeout=5
                    )
                socketio.emit("weather_update", weather)

            socketio.emit("last_updated", {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

        except Exception as e:
            print("[Monitor Error]", e)

        time.sleep(10)

# Routes
@app.route("/", methods=["GET", "POST"])
def index():
    if not session.get("logged_in"):
        return redirect("/login")
    return render_template("index.html", config=config, stock=stock, weather=weather)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == "yourmomma":
            session["logged_in"] = True
            return redirect("/")
    return render_template("login.html")

@app.route("/save_webhook", methods=["POST"])
def save_webhook():
    config["Webhook"] = request.form.get("webhook", "").strip()
    save_config(config)
    return redirect("/")

@app.route("/send_test_webhook", methods=["POST"])
def send_test_webhook():
    send_discord_alert("✅ This is a test alert from Grow a Garden Admin Panel.")
    return redirect("/")

# Discord alert function
def send_discord_alert(message):
    if config.get("Webhook"):
        try:
            requests.post(config["Webhook"], json={"content": message})
        except Exception as e:
            print("[Discord Error]", e)

# Background thread
threading.Thread(target=monitor_changes, daemon=True).start()

# 🚀 Start server with correct host/port for Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
