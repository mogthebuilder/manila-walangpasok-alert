import os
import hashlib
import requests
from playwright.sync_api import sync_playwright

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TARGET_URL = "https://www.facebook.com/iskomorenodomagoso"

SUSPENSION_KEYWORDS = [
    "walangpasok", "walang pasok", "suspension", "suspended", 
    "cancel", "cancelled", "cancellation", "no classes", 
    "suspensyon", "alternative", "alternative mode", "online classes"
]

LOCATION_KEYWORDS = [
    "manila", "maynila", "lungsod ng maynila", "metro manila", 
    "ncr", "all levels", "batang maynila", "manileño"
]

SEEN_HASHES_FILE = "seen_posts.txt"

def send_telegram_alert(text):
    message = f"🚨 *CLASS SUSPENSION / WALANG PASOK ALERT* 🚨\n\n{text[:600]}...\n\n🔗 [View Facebook Page]({TARGET_URL})"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }
    try:
        res = requests.post(url, json=payload)
        res.raise_for_status()
        print("Telegram alert sent successfully.")
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")

def get_seen_hashes():
    if os.path.exists(SEEN_HASHES_FILE):
        with open(SEEN_HASHES_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_seen_hash(post_hash):
    with open(SEEN_HASHES_FILE, "a") as f:
        f.write(f"{post_hash}\n")

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = context.new_page()
        
        print(f"Navigating to {TARGET_URL}...")
        page.goto(TARGET_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)

        # 1. JS DOM Purge: Strip popups, dialogs, comments, and sidebars directly from tree
        page.evaluate("""
            () => {
                const selectors = ['[role="dialog"]', '#login_popup', 'div[aria-label="Close"]', 'ul', 'div[role="comment"]'];
                selectors.forEach(s => document.querySelectorAll(s).forEach(el => el.remove()));
            }
        """)

        # 2. Scroll & Expand: Load cards into memory and click all "See more" triggers
        for _ in range(4):
            page.mouse.wheel(0, 1000)
            page.wait_for_timeout(1000)

        page.evaluate("""
            () => {
                const btns = Array.from(document.querySelectorAll('div[role="button"]')).filter(
                    el => el.innerText.includes('See more') || el.innerText.includes('See More')
                );
                btns.forEach(b => b.click());
            }
        """)
        page.wait_for_timeout(2000)

        # 3. Target valid post cards
        elements = page.query_selector_all('div[role="article"]')
        collected_posts = []
        for el in elements:
            text = el.inner_text().strip()
            if len(text) > 40 and text not in collected_posts:
                collected_posts.append(text)

        print(f"Total post containers extracted: {len(collected_posts)}")

        seen_hashes = get_seen_hashes()
        match_found = False

        for idx, post_text in enumerate(collected_posts[:10]):
            # SHA-256 uniquely identifies the post content
            post_hash = hashlib.sha256(post_text.encode('utf-8')).hexdigest()
            post_text_lower = post_text.lower()

            has_suspension = any(kw in post_text_lower for kw in SUSPENSION_KEYWORDS)
            has_location = any(loc in post_text_lower for loc in LOCATION_KEYWORDS)

            if has_suspension and (has_location or "#walangpasok" in post_text_lower):
                if post_hash not in seen_hashes:
                    print(f"Matching NEW post found! Sending Telegram alert...")
                    send_telegram_alert(post_text)
                    save_seen_hash(post_hash)
                    match_found = True
                    break
                else:
                    print("Matching post found, but already reported.")
                    match_found = True
                    break

        if not match_found:
            print("Checked top posts: No new suspension updates detected.")

        browser.close()

if __name__ == "__main__":
    run()
