import time
import requests
import logging
import json
import os
import re
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TimedOut
import asyncio

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
USERNAME = os.environ.get("USERNAME")
PASSWORD = os.environ.get("PASSWORD")

BASE_URL = "http://109.236.84.81"
LOGIN_PAGE_URL = BASE_URL + "/ints/login"
LOGIN_POST_URL = BASE_URL + "/ints/signin"
DATA_URL = BASE_URL + "/ints/client/res/data_smscdr.php"

bot = Bot(token=BOT_TOKEN)
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})
logging.basicConfig(level=logging.INFO, format='%(message)s')

COUNTRY_MAP = {
    "1": "🇺🇸 USA / Canada",
    "44": "🇬🇧 United Kingdom",
    "91": "🇮🇳 India",
    "880": "🇧🇩 Bangladesh",
}

def get_country_from_number(number: str) -> str:
    for code in sorted(COUNTRY_MAP.keys(), key=lambda x: -len(x)):
        if number.startswith(code):
            return COUNTRY_MAP[code]
    return '🌍 Unknown'

def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def save_already_sent(already_sent):
    with open("already_sent.json", "w") as f:
        json.dump(list(already_sent), f)

def load_already_sent():
    if os.path.exists("already_sent.json"):
        with open("already_sent.json", "r") as f:
            return set(json.load(f))
    return set()

def login():
    try:
        resp = session.get(LOGIN_PAGE_URL)
        match = re.search(r'What is (\d+) \+ (\d+)', resp.text)
        if not match:
            logging.error("Captcha not found.")
            return False
        captcha_answer = int(match.group(1)) + int(match.group(2))
        payload = {"username": USERNAME, "password": PASSWORD, "capt": captcha_answer}
        headers = {"Content-Type": "application/x-www-form-urlencoded", "Referer": LOGIN_PAGE_URL}
        resp = session.post(LOGIN_POST_URL, data=payload, headers=headers)
        if "dashboard" in resp.text.lower() or "logout" in resp.text.lower():
            logging.info("Login successful ✅")
            return True
        else:
            logging.error("Login failed ❌")
            return False
    except Exception as e:
        logging.error(f"Login error: {e}")
        return False

def build_api_url():
    return (
        f"{DATA_URL}?fdate1=2025-04-25%2000:00:00&fdate2=2026-01-01%2023:59:59&"
        "iDisplayStart=0&iDisplayLength=25&sEcho=1"
    )

def fetch_data():
    url = build_api_url()
    headers = {"X-Requested-With": "XMLHttpRequest"}
    try:
        response = session.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 403 or "login" in response.text.lower():
            logging.warning("Session expired. Re-logging...")
            if login():
                return fetch_data()
            return None
        else:
            logging.error(f"Unexpected error: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Fetch error: {e}")
        return None

already_sent = load_already_sent()

async def sent_messages():
    logging.info("🔍 Checking for messages...\n")
    data = fetch_data()
    if data and 'aaData' in data:
        for row in data['aaData']:
            date = str(row[0]).strip()
            number = str(row[2]).strip()
            service = str(row[3]).strip()
            message = str(row[4]).strip()
            match = re.search(r'\d{3}-\d{3}|\d{4,6}', message)
            otp = match.group() if match else None
            if otp:
                unique_key = f"{number}|{otp}"
                if unique_key not in already_sent:
                    already_sent.add(unique_key)
                    country = get_country_from_number(number)
                    text = (
                        "✨ <b>OTP Received</b> ✨\n\n"
                        f"⏰ <b>Time:</b> {escape_html(date)}\n"
                        f"📞 <b>Number:</b> {escape_html(number)}\n"
                        f"🌍 <b>Country:</b> {country}\n"
                        f"🔧 <b>Service:</b> {escape_html(service)}\n"
                        f"🔐 <b>OTP Code:</b> <code>{escape_html(otp)}</code>\n"
                        f"📝 <b>Msg:</b> <i>{escape_html(message)}</i>\n\n"
                        "<b>P0WERED BY</b> ROBIUL ISLAM"
                    )
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("👨‍💻 Bot Owner", url="https://t.me/robiul1515727admin")],
                        [InlineKeyboardButton("🔁 Backup Channel", url="https://t.me/robiulrl1")]
                    ])
                    try:
                        await bot.send_message(
                            chat_id=CHAT_ID,
                            text=text,
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                            reply_markup=keyboard
                        )
                        save_already_sent(already_sent)
                        logging.info(f"[+] Sent OTP: {otp}")
                    except TimedOut:
                        logging.error("Telegram TimedOut")
                    except Exception as e:
                        logging.error(f"Telegram error: {e}")
            else:
                logging.info(f"No OTP found in: {message}")
    else:
        logging.info("No data or invalid response.")

async def main():
    if login():
        while True:
            await sent_messages()
            await asyncio.sleep(3)
    else:
        logging.error("Initial login failed. Exiting...")

asyncio.run(main())
