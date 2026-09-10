import os
import hashlib
import requests

# Secrets from Environment
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
APIFY_TOKEN = os.environ.get("APIFY_TOKEN")

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

def send_telegram_alert(text, post_url=None):
    url_to_share = post_url if post_url else TARGET_URL
    message = f"🚨 *CLASS SUSPENSION / WALANG PASOK ALERT* 🚨\n\n{text[:600]}...\n\n🔗 [View Facebook Post]({url_to_share})"
    
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
    print(f"Calling Apify Facebook Scraper for {TARGET_URL}...")
    
    # Synchronous run endpoint for Apify Facebook Posts Scraper actor
    apify_url = f"https://api.apify.com/v2/acts/apify~facebook-posts-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    
    payload = {
        "startUrls": [{"url": TARGET_URL}],
        "maxPosts": 5
    }

    try:
        response = requests.post(apify_url, json=payload, timeout=120)
        response.raise_for_status()
        posts = response.json()
    except Exception as e:
        print(f"Error calling Apify API: {e}")
        return

    if not posts or not isinstance(posts, list):
        print("No posts returned from Apify.")
        return

    print(f"Successfully retrieved {len(posts)} posts from Apify.")

    seen_hashes = get_seen_hashes()
    match_found = False

    for post in posts:
        # Extract full post text from Apify JSON schema
        post_text = post.get("text") or post.get("postText") or post.get("message") or ""
        post_url = post.get("url") or post.get("postUrl") or TARGET_URL
        
        if not post_text.strip():
            continue

        # SHA-256 Hash for deduplication
        post_hash = hashlib.sha256(post_text.encode('utf-8')).hexdigest()
        post_text_lower = post_text.lower()

        has_suspension = any(kw in post_text_lower for kw in SUSPENSION_KEYWORDS)
        has_location = any(loc in post_text_lower for loc in LOCATION_KEYWORDS)

        if has_suspension and (has_location or "#walangpasok" in post_text_lower):
            if post_hash not in seen_hashes:
                print("Matching NEW suspension post detected! Sending Telegram alert...")
                send_telegram_alert(post_text, post_url)
                save_seen_hash(post_hash)
                match_found = True
                break
            else:
                print("Matching suspension post found, but already reported.")
                match_found = True
                break

    if not match_found:
        print("Checked latest posts: No new suspension updates detected.")

if __name__ == "__main__":
    run()
