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
    message = f"🚨 *CLASS SUSPENSION / WALANG PASOK ALERT* 🚨\n\n{text[:500]}...\n\n🔗 [View Facebook Page]({TARGET_URL})"
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
        # Mobile viewport forces Facebook to render lightweight HTML without strict login popups
        context = browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        )
        page = context.new_page()
        
        print(f"Navigating to {TARGET_URL}...")
        page.goto(TARGET_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Attempt to dismiss Facebook login overlays if rendered
        try:
            close_button = page.query_selector('div[aria-label="Close"]') or page.query_selector('i[class*="x1b0d499"]')
            if close_button:
                close_button.click()
                print("Dismissed Facebook login popup.")
        except Exception:
            pass

        # Scroll down to pull past pinned posts into the DOM
        for _ in range(5):
            page.mouse.wheel(0, 1200)
            page.wait_for_timeout(1000)

        # Target post elements by accessibility role
        posts = page.query_selector_all('div[role="article"]')
        if not posts:
            print("No posts found or page failed to load.")
            browser.close()
            return

        last_seen = get_last_seen()
        match_found = False

        # Scan through the top 10 recent posts
        for post in posts[:10]:
            post_text = post.inner_text()
            post_snippet = post_text[:100].replace("\n", " ")
            post_text_lower = post_text.lower()

            # Check for suspension and location keyword matches
            has_suspension = any(kw.lower() in post_text_lower for kw in SUSPENSION_KEYWORDS)
            has_location = any(loc.lower() in post_text_lower for loc in LOCATION_KEYWORDS)

            if has_suspension and has_location:
                if post_snippet != last_seen:
                    print("Matching new post found! Sending Telegram alert...")
                    send_telegram_alert(post_text)
                    save_last_seen(post_snippet)
                    match_found = True
                    break  # Stop checking once the newest alert is handled
                else:
                    print("Matching post found, but it has already been reported.")
                    match_found = True
                    break

        if not match_found:
            print("Checked top 10 posts: No relevant class suspension updates detected.")
            # Record the latest top post snippet to maintain accurate state tracking
            top_snippet = posts[0].inner_text()[:100].replace("\n", " ")
            if top_snippet != last_seen:
                save_last_seen(top_snippet)

        browser.close()

if __name__ == "__main__":
    run()
