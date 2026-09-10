import os
import re
import requests
from playwright.sync_api import sync_playwright

# Telegram Environment Secrets
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Target Facebook Page
TARGET_URL = "https://www.facebook.com/iskomorenodomagoso"

# Primary suspension action triggers
SUSPENSION_KEYWORDS = [
    "walangpasok",
    "walang pasok",
    "suspension",
    "suspended",
    "cancel",
    "cancelled",
    "cancellation",
    "no classes",
    "suspensyon",
    "alternative",
    "alternative mode",
    "online classes"
]

# Location/Scope keywords to prevent irrelevant alerts
LOCATION_KEYWORDS = [
    "manila",
    "maynila",
    "lungsod ng maynila",
    "metro manila",
    "ncr",
    "all levels"
]

LAST_POST_FILE = "last_post.txt"

def send_telegram_alert(text):
    message = f"🚨 *CLASS SUSPENSION / WALANG PASOK ALERT* 🚨\n\n{text[:500]}...\n\n🔗 [View Facebook Post]({TARGET_URL})"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("Telegram alert sent successfully.")
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")

def get_last_seen():
    if os.path.exists(LAST_POST_FILE):
        with open(LAST_POST_FILE, "r") as f:
            return f.read().strip()
    return ""

def save_last_seen(post_snippet):
    with open(LAST_POST_FILE, "w") as f:
        f.write(post_snippet)

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print(f"Navigating to {TARGET_URL}...")
        page.goto(TARGET_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        # Target post elements by accessibility role
        posts = page.query_selector_all('div[role="article"]')
        if not posts:
            print("No posts found or page failed to load.")
            browser.close()
            return

        latest_post = posts[0].inner_text()
        post_snippet = latest_post[:100].replace("\n", " ")

        last_seen = get_last_seen()

        # Check if the top post is new
        if post_snippet != last_seen:
            print("New post detected! Checking keywords...")
            post_text_lower = latest_post.lower()

            # Check if any suspension keyword matches
            has_suspension_keyword = any(kw.lower() in post_text_lower for kw in SUSPENSION_KEYWORDS)
            
            # Check if any location keyword matches
            has_location_keyword = any(loc.lower() in post_text_lower for loc in LOCATION_KEYWORDS)

            if has_suspension_keyword and has_location_keyword:
                print("Matching post found! Sending Telegram alert...")
                send_telegram_alert(latest_post)
            else:
                print("New post found, but no matching suspension keywords.")

            save_last_seen(post_snippet)
        else:
            print("No new posts since last check.")

        browser.close()

if __name__ == "__main__":
    run()
