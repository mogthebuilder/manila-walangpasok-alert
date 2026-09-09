import os
import re
import requests
from playwright.sync_api import sync_playwright

# Telegram Environment Secrets
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

TARGET_URL = "https://www.facebook.com/EmiCalixtoRubiano"
KEYWORDS = ["walang pasok", "suspension", "suspended", "class suspension"]

LAST_POST_FILE = "last_post.txt"

def send_telegram_alert(text):
    message = f"🚨 *WALANG PASOK / ALERT DETECTED* 🚨\n\n{text[:500]}...\n\n🔗 [View Facebook Page]({TARGET_URL})"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }
    requests.post(url, json=payload)

def get_last_seen():
    if os.path.exists(LAST_POST_FILE):
        with open(LAST_POST_FILE, "r") as f:
            return f.read().strip()
    return ""

def save_last_seen(post_id):
    with open(LAST_POST_FILE, "w") as f:
        f.write(post_id)

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto(TARGET_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        posts = page.query_selector_all('div[role="article"]')
        if not posts:
            print("No posts found.")
            browser.close()
            return

        latest_post = posts[0].inner_text()
        post_snippet = latest_post[:100].replace("\n", " ")

        last_seen = get_last_seen()

        # Check if the post is new
        if post_snippet != last_seen:
            print("New post detected! Checking keywords...")
            # Keyword matching
            if any(re.search(rf"\b{kw}\b", latest_post, re.IGNORECASE) for kw in KEYWORDS):
                print("Keyword match! Sending Telegram alert...")
                send_telegram_alert(latest_post)
            else:
                print("No relevant keywords found.")
            
            save_last_seen(post_snippet)
        else:
            print("No new posts since last check.")

        browser.close()

if __name__ == "__main__":
    run()
