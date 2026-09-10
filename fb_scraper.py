import os
import re
import requests
from playwright.sync_api import sync_playwright

# Telegram Environment Secrets
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Target Facebook Page (Using mbasic interface for stable headless parsing)
TARGET_URL = "https://mbasic.facebook.com/iskomorenodomagoso"

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
    message = f"🚨 *CLASS SUSPENSION / WALANG PASOK ALERT* 🚨\n\n{text[:500]}...\n\n🔗 [View Facebook Page](https://www.facebook.com/iskomorenodomagoso)"
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
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print(f"Navigating to {TARGET_URL}...")
        page.goto(TARGET_URL, wait_until="networkidle")
        page.wait_for_timeout(3000)

        # Multi-selector strategy: Check mbasic containers, article roles, and standard div posts
        posts = page.query_selector_all('article, div[role="article"], div[id*="u_0_"], div.story_body_container')
        
        if not posts:
            # Fallback to direct page text evaluation if specific containers are hidden
            print("Specific post containers not detected. Evaluating body text...")
            body_element = page.query_selector("body")
            if body_element:
                posts = [body_element]
            else:
                print("No posts found or page failed to load.")
                browser.close()
                return

        last_seen = get_last_seen()
        match_found = False

        # Scan through detected post containers
        for post in posts[:10]:
            post_text = post.inner_text()
            if not post_text.strip():
                continue

            post_snippet = post_text[:100].replace("\n", " ")
            post_text_lower = post_text.lower()

            # Check for keyword matches
            has_suspension = any(kw.lower() in post_text_lower for kw in SUSPENSION_KEYWORDS)
            has_location = any(loc.lower() in post_text_lower for loc in LOCATION_KEYWORDS)

            if has_suspension and has_location:
                if post_snippet != last_seen:
                    print("Matching new post found! Sending Telegram alert...")
                    send_telegram_alert(post_text)
                    save_last_seen(post_snippet)
                    match_found = True
                    break
                else:
                    print("Matching post found, but it has already been reported.")
                    match_found = True
                    break

        if not match_found:
            print("Checked recent posts: No relevant class suspension updates detected.")
            top_text = posts[0].inner_text()
            if top_text.strip():
                top_snippet = top_text[:100].replace("\n", " ")
                if top_snippet != last_seen:
                    save_last_seen(top_snippet)

        browser.close()

if __name__ == "__main__":
    run()
