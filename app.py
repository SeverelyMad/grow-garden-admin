from flask import Flask, render_template, jsonify
import requests
from bs4 import BeautifulSoup
import json

app = Flask(__name__)
CONFIG_FILE = "config.json"
WEBHOOK_SENT_FILE = "sent_log.json"

def read_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def read_sent_log():
    try:
        with open(WEBHOOK_SENT_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def write_sent_log(data):
    with open(WEBHOOK_SENT_FILE, "w") as f:
        json.dump(data, f, indent=2)

def fetch_stock():
    html = requests.get("https://growagarden.gg/stocks").text
    soup = BeautifulSoup(html, "html.parser")
    stock = {}
    for section in soup.select('.stock-section'):
        title = section.h2.get_text(strip=True)
        items = {}
        for li in section.select('li'):
            if 'x' in li.text:
                name = li.span.text.strip()
                qty = int(li.text.strip().split('x')[-1])
                items[name] = qty
        stock[title] = items
    return stock

def fetch_weather():
    html = requests.get("https://growagarden.gg/weather").text
    soup = BeautifulSoup(html, "html.parser")
    event_el = soup.select_one('.weather-event')
    return {
        "active": event_el is not None,
        "event": event_el.get_text(strip=True) if event_el else None
    }

@app.route("/")
def index():
    config = read_config()
    stock = fetch_stock()
    weather = fetch_weather()
    return render_template("index.html", config=config, stock=stock, weather=weather)

@app.route("/api/data")
def api_data():
    return jsonify({
        "stock": fetch_stock(),
        "weather": fetch_weather()
    })


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run(port=5000)