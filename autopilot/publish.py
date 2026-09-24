"""Posting to free platform APIs. Every platform is optional: no credentials = skipped."""
import time
from pathlib import Path

import requests

from . import config

UTM = "utm_source={src}&utm_medium=organic&utm_campaign={camp}"


def link_for(post: dict, source: str) -> str:
    sep = "&" if "?" in post["link"] else "?"
    return post["link"] + sep + UTM.format(src=source, camp=post["type"])


def hashtags(post: dict, n=7) -> str:
    return " ".join("#" + t for t in post["hashtags"][:n])


def raw_url(rel_path: str) -> str:
    return f"https://raw.githubusercontent.com/{config.GITHUB_REPOSITORY}/{config.GITHUB_BRANCH}/{rel_path}"


def wait_for_url(url: str, tries=15) -> bool:
    for _ in range(tries):
        try:
            if requests.get(url, timeout=20, stream=True).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(6)
    return False


# ---------------- Telegram ----------------
def _tg(method: str, **kw):
    r = requests.post(f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/{method}", timeout=120, **kw)
    r.raise_for_status()
    return r.json()


def telegram_send(chat_id: str, image: Path, caption: str, video: Path | None = None):
    with open(image, "rb") as f:
        _tg("sendPhoto", data={"chat_id": chat_id, "caption": caption[:1000]}, files={"photo": f})
    if video and video.exists():
        with open(video, "rb") as f:
            _tg("sendVideo", data={"chat_id": chat_id, "caption": "9:16 video for Reels / TikTok / Shorts"}, files={"video": f})


# ---------------- Facebook Page ----------------
def facebook(post: dict, image_url: str) -> str:
    cap = f"{post['caption']}\n\n{link_for(post, 'facebook')}\n\n{hashtags(post, 5)}"
    r = requests.post(f"https://graph.facebook.com/{config.GRAPH_VERSION}/{config.FB_PAGE_ID}/photos",
                      data={"url": image_url, "caption": cap, "access_token": config.FB_PAGE_TOKEN}, timeout=60)
    r.raise_for_status()
    return r.json().get("post_id") or r.json().get("id", "")


# ---------------- Instagram ----------------
def _ig_wait(creation_id: str, tries=30):
    for _ in range(tries):
        r = requests.get(f"https://graph.facebook.com/{config.GRAPH_VERSION}/{creation_id}",
                         params={"fields": "status_code", "access_token": config.FB_PAGE_TOKEN}, timeout=30)
        code = r.json().get("status_code", "")
        if code == "FINISHED":
            return True
        if code == "ERROR":
            return False
        time.sleep(8)
    return False


def instagram(post: dict, image_url: str | None = None, video_url: str | None = None) -> str:
    cap = f"{post['caption']}\n\nLink in bio.\n\n{hashtags(post, 7)}"
    base = f"https://graph.facebook.com/{config.GRAPH_VERSION}/{config.IG_USER_ID}"
    data = {"caption": cap, "access_token": config.FB_PAGE_TOKEN}
    if video_url:
        data.update({"media_type": "REELS", "video_url": video_url, "share_to_feed": "true"})
    else:
        data["image_url"] = image_url
    r = requests.post(base + "/media", data=data, timeout=60)
    r.raise_for_status()
    cid = r.json()["id"]
    if not _ig_wait(cid):
        raise RuntimeError("Instagram container not ready")
    r = requests.post(base + "/media_publish", data={"creation_id": cid, "access_token": config.FB_PAGE_TOKEN}, timeout=60)
    r.raise_for_status()
    return r.json().get("id", "")


# ---------------- Pinterest ----------------
def _pin_refresh() -> str | None:
    if not (config.PINTEREST_REFRESH_TOKEN and config.PINTEREST_APP_ID and config.PINTEREST_APP_SECRET):
        return None
    r = requests.post(f"{config.PINTEREST_API_BASE}/oauth/token", auth=(config.PINTEREST_APP_ID, config.PINTEREST_APP_SECRET),
                      data={"grant_type": "refresh_token", "refresh_token": config.PINTEREST_REFRESH_TOKEN}, timeout=30)
    return r.json().get("access_token") if r.ok else None


def pinterest(post: dict, image_url: str) -> str:
    body = {"board_id": config.PINTEREST_BOARD_ID, "title": post["headline"][:100],
            "description": (post["caption"] + "\n\n" + hashtags(post, 5))[:500],
            "link": link_for(post, "pinterest"),
            "media_source": {"source_type": "image_url", "url": image_url}}
    token = config.PINTEREST_ACCESS_TOKEN
    for attempt in range(2):
        r = requests.post(f"{config.PINTEREST_API_BASE}/pins", json=body,
                          headers={"Authorization": f"Bearer {token}"}, timeout=60)
        if r.status_code == 401 and attempt == 0:
            token = _pin_refresh() or token
            continue
        r.raise_for_status()
        return r.json().get("id", "")
    return ""


def enabled_platforms() -> list:
    out = []
    if config.FB_PAGE_ID and config.FB_PAGE_TOKEN:
        out.append("facebook")
    if config.IG_USER_ID and config.FB_PAGE_TOKEN:
        out.append("instagram" + ("+reels" if config.IG_REELS else ""))
    if config.PINTEREST_ACCESS_TOKEN and config.PINTEREST_BOARD_ID:
        out.append("pinterest")
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHANNEL_ID:
        out.append("telegram-channel")
    return out
