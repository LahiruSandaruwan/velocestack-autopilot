"""Auto-discovers every public product in the Fourthwall shop (so new products get promoted automatically)."""
import html
import json
import re

import requests

from . import config

UA = {"User-Agent": "Mozilla/5.0 (compatible; VeloceStackAutopilot/1.0)"}
CATALOG_FILE = config.DATA_DIR / "catalog.json"


def _meta(page: str, prop: str) -> str:
    for pat in (r'<meta[^>]+(?:property|name)="%s"[^>]+content="([^"]*)"' % re.escape(prop),
                r'<meta[^>]+content="([^"]*)"[^>]+(?:property|name)="%s"' % re.escape(prop)):
        m = re.search(pat, page)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""


def short_name(title: str) -> str:
    t = re.split(r"\s[|–—]\s|:\s", title)[0].strip()
    return t or title


def _load_cached() -> list:
    try:
        return json.loads(CATALOG_FILE.read_text())
    except Exception:
        return []


def sync() -> list:
    """Return list of products: {slug,title,short,description,image,price,url}. Falls back to the cached file."""
    if config.OFFLINE:
        return _load_cached()
    try:
        home = requests.get(config.SHOP_URL + "/", headers=UA, timeout=30).text
        slugs = []
        for s in re.findall(r"/products/([a-z0-9][a-z0-9-]*)", home):
            if s not in slugs:
                slugs.append(s)
        items = []
        for slug in slugs:
            url = f"{config.SHOP_URL}/products/{slug}"
            page = requests.get(url, headers=UA, timeout=30).text
            title = _meta(page, "og:title")
            if not title:
                continue
            price = ""
            m = re.search(r'"price":\s*"?([0-9]+(?:\.[0-9]+)?)', page)
            if m:
                price = m.group(1)
            items.append({
                "slug": slug, "title": title, "short": short_name(title),
                "description": _meta(page, "og:description")[:400],
                "image": _meta(page, "og:image"), "price": price, "url": url,
            })
        if items:
            config.DATA_DIR.mkdir(parents=True, exist_ok=True)
            CATALOG_FILE.write_text(json.dumps(items, indent=1))
            return items
    except Exception as e:  # network hiccup: keep going with the last known catalog
        print("catalog sync failed:", e)
    return _load_cached()


def fmt_price(p: str) -> str:
    if not p:
        return ""
    try:
        v = float(p)
        return f"${v:.0f}" if v == int(v) else f"${v:.2f}"
    except ValueError:
        return ""
