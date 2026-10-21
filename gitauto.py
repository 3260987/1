import hashlib
import json
import os
import time
import feedparser
import requests

FEEDS = [    
"https://rss.buzzsprout.com/1241654.rss",
"https://anchor.fm/s/2e3159d8/podcast/rss",
"https://psycyb.libsyn.com/rss",
"https://feeds.simplecast.com/iTYwWFdE",
"https://rss.buzzsprout.com/1035529.rss",
"https://rss.buzzsprout.com/1635619.rss",
"https://feeds.megaphone.fm/8th-layer-insights",
"https://feeds.buzzsprout.com/1431304.rss",
"https://www.spreaker.com/show/4573919/episodes/feed",
"http://wfpusa.libsyn.com/rss",
"https://anchor.fm/s/332ace24/podcast/rss",
"https://anchor.fm/s/272ae0dc/podcast/rss",
"https://zeroday.podbean.com/feed.xml",
"https://feeds.megaphone.fm/darknetdiaries",

    
]

STATE_FILE = "seen.json"
DOWNLOAD_DIR = "podcasts"  # חייב להיות תואם למה שה-Workflow מחפש
TEST_SEND = os.environ.get("TEST_SEND") == "true"


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def clean_name(name, feed_url=""):
    hebrew_map = {
        'א': 'a', 'ב': 'b', 'ג': 'g', 'ד': 'd', 'ה': 'h', 'ו': 'v', 'ז': 'z',
        'ח': 'ch', 'ט': 't', 'י': 'y', 'כ': 'k', 'ך': 'k', 'ל': 'l', 'מ': 'm',
        'ם': 'm', 'נ': 'n', 'ן': 'n', 'ס': 's', 'ע': 'a', 'פ': 'p', 'ף': 'p',
        'צ': 'ts', 'ץ': 'ts', 'ק': 'k', 'ר': 'r', 'ש': 'sh', 'ת': 't'
    }
    
    # הסרת תווים אסורים פשוטים מראש
    for char in ['[', ']', ':', ',', '?', '!', '"', "'", '|', '\\', '/']:
        name = name.replace(char, '')

    transliterated = "".join(hebrew_map.get(c, c) for c in name)
    safe_ascii = "".join(c for c in transliterated if c.isascii() and (c.isalnum() or c in " -_()."))
    safe_ascii = safe_ascii.strip()
    
    if not safe_ascii and feed_url:
        safe_ascii = "podcast_" + hashlib.md5(feed_url.encode()).hexdigest()[:8]
    elif not safe_ascii:
        safe_ascii = "podcast"
        
    return safe_ascii


def download_podcast(url, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for attempt in range(1, 4):
        try:
            with requests.get(url, headers=headers, stream=True, timeout=300) as r:
                r.raise_for_status()
                with open(path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 512):
                        if chunk:
                            f.write(chunk)
            return path
        except Exception as e:
            print(f"ניסיון {attempt} נכשל בהורדה: {e}")
            if attempt == 3:
                raise e
            time.sleep(5)


def process_entry(feed_url, feed_title, entry):
    title = entry.get("title", "New episode")
    enclosures = entry.get("enclosures", [])
    if not enclosures:
        print(f"No audio file found for: {title}")
        return

    cleaned_feed = clean_name(feed_title, feed_url)[:50].strip()
    cleaned_title = clean_name(title, feed_url)[:70].strip()

    # יצירת תיקייה נפרדת לכל פודקאסט תחת podcasts
    show_dir = os.path.join(DOWNLOAD_DIR, cleaned_feed)
    filename = f"{cleaned_title}.mp3"
    path = os.path.join(show_dir, filename)

    print(f"Downloading to [{cleaned_feed}]: {filename}")
    try:
        download_podcast(enclosures[0]["href"], path)
    except Exception as e:
        print(f"Failed to download {filename}: {e}")


def main():
    state = load_state()
    for feed_url in FEEDS:
        if not feed_url.strip():
            continue

        parsed = feedparser.parse(feed_url)
        if not parsed.entries:
            continue

        feed_title = parsed.feed.get("title", "Podcast")
        entries = parsed.entries
        ids = [e.get("id") or e.get("link") for e in entries]

        if TEST_SEND and entries:
            process_entry(feed_url, feed_title, entries[0])
            state.setdefault(feed_url, ids)
            continue

        if feed_url not in state:
            state[feed_url] = ids
            continue

        seen = set(state[feed_url])
        for entry, eid in reversed(list(zip(entries, ids))):
            if eid not in seen:
                process_entry(feed_url, feed_title, entry)
                seen.add(eid)
        state[feed_url] = list(seen)

    save_state(state)


if __name__ == "__main__":
    main()
