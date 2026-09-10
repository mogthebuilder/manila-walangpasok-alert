import os
import requests
from playwright.sync_api import sync_playwright

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TARGET_URL = "https://www.facebook.com/iskomorenodomagoso"

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

LOCATION_KEYWORDS = [
    "manila",
    "maynila",
    "lungsod ng maynila",
    "metro manila",
    "ncr",
    "all levels",
    "batang maynila",
    "manileño"
]

LAST_POST_FILE = "last_post.txt"

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

        # Clear login overlays
        page.evaluate("""
            () => {
                const selectors = ['[role="dialog"]', '#login_popup', 'div[aria-label="Close"]'];
                selectors.forEach(selector => {
                    document.querySelectorAll(selector).forEach(el => el.remove());
                });
            }
        """)

        # Scroll to load post cards
        for _ in range(4):
            page.mouse.wheel(0, 1000)
            page.wait_for_timeout(1000)

        # Force expand all "See more" text collapses directly via JS
        page.evaluate("""
            () => {
                const seeMoreBtns = Array.from(document.querySelectorAll('div[role="button"]')).filter(
                    el => el.innerText.includes('See more') || el.innerText.includes('See More')
                );
                seeMoreBtns.forEach(btn => btn.click());
            }
        """)
        page.wait_for_timeout(2000)

        # Extract articles while ignoring user comment threads
        elements = page.query_selector_all('div[role="article"]')
        collected_posts = []
        for el in elements:
            text = el.inner_text().strip()
            # Verify the element originates from the page author rather than a comment
            if text and "Isko Moreno Domagoso" in text and text not in collected_posts:
                collected_posts.append(text)

        print(f"Total valid author posts extracted: {len(collected_posts)}")

        last_seen = get_last_seen()
        match_found = False

        for idx, post_text in enumerate(collected_posts[:10]):
            post_snippet = post_text[:100].replace("\n", " ")
            post_text_lower = post_text.lower()

            has_suspension = any(kw.lower() in post_text_lower for kw in SUSPENSION_KEYWORDS)
            has_location = any(loc.lower() in post_text_lower for loc in LOCATION_KEYWORDS)

            if has_suspension and (has_location or "#walangpasok" in post_text_lower):
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
            if collected_posts:
                top_snippet = collected_posts[0][:100].replace("\n", " ")
                if top_snippet != last_seen:
                    save_last_seen(top_snippet)

        browser.close()

if __name__ == "__main__":
    run()
