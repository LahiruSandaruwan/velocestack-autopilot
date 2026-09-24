"""Central config. Everything is read from environment variables (GitHub Secrets / Variables)."""
import os
from pathlib import Path


def env(key: str, default: str = "") -> str:
    v = os.environ.get(key)
    return v.strip() if v and v.strip() else default


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(env("DATA_DIR", str(ROOT / "data")))
POSTS_DIR = Path(env("POSTS_DIR", str(ROOT / "posts")))
DOCS_DIR = Path(env("DOCS_DIR", str(ROOT / "docs")))

# review = send drafts only to your private Telegram chat (safe default)
# auto   = post to every platform that has credentials
MODE = env("MODE", "review").lower()
OFFLINE = env("OFFLINE") == "1"  # no network for catalog / LLM (local testing)

SHOP_URL = env("SHOP_URL", "https://velocestack-shop.fourthwall.com").rstrip("/")
BRAND = env("BRAND", "VeloceStack")

# ---- LLM (free tier) ----
GEMINI_API_KEY = env("GEMINI_API_KEY")
GEMINI_MODELS = [m for m in [env("GEMINI_MODEL"), "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"] if m]

# ---- Telegram (free, no approval) ----
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = env("TELEGRAM_CHAT_ID")          # your private chat: receives drafts / logs
TELEGRAM_CHANNEL_ID = env("TELEGRAM_CHANNEL_ID")    # optional public channel: gets posts in auto mode

# ---- Meta (Facebook Page + Instagram) ----
FB_PAGE_ID = env("FB_PAGE_ID")
FB_PAGE_TOKEN = env("FB_PAGE_TOKEN")
IG_USER_ID = env("IG_USER_ID")
IG_REELS = env("IG_REELS") == "1"                   # also publish the 9:16 video as a Reel
GRAPH_VERSION = env("GRAPH_VERSION", "v23.0")

# ---- Pinterest ----
PINTEREST_ACCESS_TOKEN = env("PINTEREST_ACCESS_TOKEN")
PINTEREST_BOARD_ID = env("PINTEREST_BOARD_ID")
PINTEREST_API_BASE = env("PINTEREST_API_BASE", "https://api.pinterest.com/v5")
PINTEREST_REFRESH_TOKEN = env("PINTEREST_REFRESH_TOKEN")
PINTEREST_APP_ID = env("PINTEREST_APP_ID")
PINTEREST_APP_SECRET = env("PINTEREST_APP_SECRET")

# ---- Where generated images live (GitHub provides these inside Actions) ----
GITHUB_REPOSITORY = env("GITHUB_REPOSITORY")        # owner/repo
GITHUB_BRANCH = env("GITHUB_REF_NAME", "main")

# Free guides (Gumroad lead magnets). These feed the "free -> paid" funnel.
FREE_GUIDES = [
    {"key": "email", "title": "21 Email Marketing Hacks",
     "url": "https://velocestack.gumroad.com/l/sbgmri",
     "blurb": "21 short, practical email marketing tactics you can apply one at a time."},
    {"key": "dictionary", "title": "The Internet Marketing Dictionary",
     "url": "https://velocestack.gumroad.com/l/yitpw",
     "blurb": "102 marketing terms explained in plain English, A to Z."},
    {"key": "tools", "title": "101 Free Online Marketing Tools",
     "url": "https://velocestack.gumroad.com/l/skfjon",
     "blurb": "A zero-budget starter toolkit of 101 free marketing tools."},
]
TYPE_TO_GUIDE = {"tip": "email", "term": "dictionary", "tool": "tools"}

# 14 slots = 7 days x 2 posts. ~50% education, ~21% free guides, ~29% paid products.
PATTERN = ["tip", "product", "term", "freebie", "tool", "product", "tip",
           "freebie", "term", "product", "tool", "tip", "freebie", "product"]

BANNED_WORDS = ["guaranteed", "get rich", "passive income guaranteed", "100% profit", "no risk",
                "make $", "earn $", "cure", "miracle"]
