#!/usr/bin/env python3
"""
scraper_service.py

- Uses Selenium to load a JS-rendered page and BeautifulSoup to parse it.
- Keeps latest_data in memory, atomically writes crypto_data.json (and backup).
- Provides Flask endpoints:
    GET /latest  -> returns the latest JSON (raw)
    GET /health  -> returns simple health status
- Fault tolerant: retries, keeps last_valid_data, can restart the webdriver on errors.
"""
import os
import tempfile
import shutil
import json
import time
import threading
import signal
from threading import Lock, Thread
import random

from flask import Flask, jsonify, Response

from bs4 import BeautifulSoup

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# -------------------------
# CONFIG (edit as needed)
# -------------------------
TARGET_URL = "https://www.binance.com/en/markets"

ROW_SELECTOR = "div.overview-table-row"
POLL_INTERVAL = 2.0               
INITIAL_LOAD_DELAY = 5.0          
JSON_FILE = "crypto_data.json"
BACKUP_FILE = "crypto_data_backup.json"

MAX_ROWS = None

# -------------------------
# Global state
# -------------------------
latest_data = []          
latest_data_lock = Lock()
stop_event = threading.Event()

# -------------------------
# Helpers: atomic save
# -------------------------
def save_json_atomic(path, data, backup_path=None):
    """
    Atomically write JSON to 'path'. Keep a backup if backup_path is provided.
    Create temp file in same directory to avoid cross-drive issues on Windows.
    """
    if not data:
        return

    dir_path = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        if backup_path and os.path.exists(path):
            try:
                shutil.copy2(path, backup_path)
            except Exception as e:
                print("Warning: failed to write backup:", e)
        os.replace(tmp_path, path)
    except Exception as e:
        print("Error saving JSON atomically:", e)
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

# -------------------------
# Selenium driver creation
# -------------------------
def create_driver():
    """Create a Chrome webdriver (headless)."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3")
    # In some environments may need:
    # options.add_argument("--disable-gpu")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    return driver

# -------------------------
# Scraping/parsing function
# -------------------------
def parse_market_from_html(html):
    """
    Parse page HTML with BeautifulSoup and return a list of dicts:
    [{"pair": "...", "price": "...", "change_24h": "..."}, ...]
    Adjust parsing logic depending on target site structure.
    """
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select(ROW_SELECTOR)
    results = []
    for row in rows:
        text = row.get_text(separator="\n").strip()
        parts = [p.strip() for p in text.split("\n") if p.strip() != ""]
        if len(parts) >= 3:
            pair = parts[0]
            price = parts[1]
            change_24h = parts[2]
            results.append({"pair": pair, "price": price, "change_24h": change_24h})
        if MAX_ROWS and len(results) >= MAX_ROWS:
            break
    return results

# -------------------------
# Main scraping loop
# -------------------------
def scrape_loop():
    """
    Background loop: maintain webdriver, fetch page_source, parse with BS,
    update latest_data (with lock) and atomically write JSON files.
    """
    global latest_data
    driver = None
    backoff = 1.0

    while not stop_event.is_set():
        try:
            if driver is None:
                print("Starting webdriver...")
                driver = create_driver()
                driver.get(TARGET_URL)
                time.sleep(INITIAL_LOAD_DELAY)  
            else:
                try:
                    driver.execute_script("window.scrollTo(0, 0);")
                except Exception:
                    pass

            html = driver.page_source
            parsed = parse_market_from_html(html)

            if parsed:
                with latest_data_lock:
                    latest_data = parsed
                save_json_atomic(JSON_FILE, latest_data, backup_path=BACKUP_FILE)
                print(f"Saved {len(latest_data)} items to {JSON_FILE}")
                backoff = 1.0
            else:
                
                with latest_data_lock:
                    to_save = latest_data.copy()
                if to_save:
                    save_json_atomic(JSON_FILE, to_save, backup_path=BACKUP_FILE)
                    print("⚠️ Parsed empty this iteration — re-saved last valid snapshot.")
                else:
                    print("⚠️ Parsed empty and no last valid snapshot available yet.")

            
            for _ in range(int(POLL_INTERVAL * 10)):
                if stop_event.is_set():
                    break
                time.sleep(0.1)

        except Exception as e:
            print("Scraper loop caught exception:", repr(e))
            
            try:
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass
                driver = None
            except Exception:
                driver = None

        
            with latest_data_lock:
                if latest_data:
                    save_json_atomic(JSON_FILE, latest_data, backup_path=BACKUP_FILE)
                    print("Saved last valid snapshot after error.")
            time.sleep(min(backoff, 30))
            backoff *= 2.0
            continue

    
    try:
        if driver:
            driver.quit()
    except Exception:
        pass
    print("Scraper loop stopped.")

# -------------------------
# Background updater
# -------------------------
def update_data_loop():
    global latest_data
    while not stop_event.is_set():
        # Simulate new scraped data
        new_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "price": round(random.uniform(50000, 60000), 2),
            "volume": random.randint(1000, 5000)
        }
        with latest_data_lock:
            latest_data = new_data
        print(f"Data updated: {latest_data}")
        time.sleep(POLL_INTERVAL)



# -------------------------
# Flask API
# -------------------------
app = Flask(__name__)

    

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/htmlpage", methods=["GET"])
def get_html_page():
    with latest_data_lock:
        if not latest_data:
            return jsonify({"error": "No data yet"}), 503
        
        html_content = """
        <meta http-equiv="refresh" content="1">
        <h2>Crypto Market Data</h2>
        <p>Last updated: {timestamp}</p>
        <table border="1" cellpadding="5" cellspacing="0">
            <tr>
                <th>Pair</th>
                <th>Price</th>
                <th>Change (24h)</th>
            </tr>
            {rows}
        </table>
        """.format(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            rows="".join("<tr><td>{pair}</td><td>{price}</td><td>{change_24h}</td></tr>".format(**item) for item in latest_data)
        )
        return html_content

@app.route("/latest", methods=["GET"])
def get_latest():
    with latest_data_lock:
        if not latest_data:
            return jsonify({"error": "No data yet"}), 503
        return jsonify({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(latest_data),
            "data": latest_data
        })
        return """<meta http-equiv="refresh" content="1" /> """

# -------------------------
# Graceful shutdown handling
# -------------------------
def handle_signal(sig, frame):
    print("Signal received, stopping...")
    stop_event.set()

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

# -------------------------
# Main entry
# -------------------------

if __name__ == "__main__":
    
    t = Thread(target=scrape_loop, daemon=True)
    t.start()

   
    print("Starting Flask server on http://0.0.0.0:5000 ...")
    try:
        app.run(host="0.0.0.0", port=5000, threaded=True)
    finally:
        stop_event.set()
        t.join(timeout=5)
        print("Exiting.")
