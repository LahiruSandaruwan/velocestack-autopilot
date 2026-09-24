"""Decides WHAT to post and writes the copy (free Gemini tier, with an offline fallback)."""
import json
import random
import re

import requests

from . import config
from .catalog import fmt_price

VOICE = (
    "Brand voice: friendly, practical, plain English, no hype. Audience: creators, freelancers and small "
    "online sellers. Never promise income or results. No URLs, no hashtags inside the text fields, at most "
    "one emoji. Do not invent facts, numbers, discounts or features."
)

LABELS = {"tip": "EMAIL TIP", "term": "MARKETING TERM", "tool": "FREE TOOL", "product": "IN THE STORE",
          "freebie": "FREE GUIDE"}

# ---------------- offline fallback pools (used when no API key / API error) ----------------
OFFLINE_TIPS = [
    ("subject-lines-like-headlines", "Write subject lines like headlines", "Be specific, use numbers and keep it under about 50 characters."),
    ("welcome-email-fast", "Send the welcome email immediately", "The first email gets the best open rate. Deliver the gift and introduce yourself."),
    ("one-email-one-goal", "One email, one goal", "Give every message a single main call to action so readers know the next step."),
    ("ask-a-question", "Ask a simple question", "A reply-worthy question starts a conversation and helps inbox placement."),
    ("add-a-ps", "Add a P.S.", "The postscript is one of the most read parts of an email. Put your best nudge there."),
    ("clean-list", "Clean your list twice a year", "Remove people who never open so your delivery stays healthy."),
    ("test-one-thing", "Test one thing at a time", "Change the subject, the offer or the button, not all three at once."),
    ("steady-schedule", "Send on a steady schedule", "Weekly beats random bursts. Readers learn when to expect you."),
]
OFFLINE_TERMS = [
    ("ab-test", "A/B test", "Comparing two versions of a page, ad or email to see which performs better."),
    ("cta", "Call to action (CTA)", "The button or line that tells people what to do next, like Download or Sign up."),
    ("conversion-rate", "Conversion rate", "The share of visitors who take the action you wanted, such as buying."),
    ("lead-magnet", "Lead magnet", "A free gift, like a checklist, offered in exchange for an email address."),
    ("bounce-rate", "Bounce rate", "The percentage of visitors who leave after viewing only one page."),
    ("evergreen-content", "Evergreen content", "Content that stays useful for months or years, not just this week."),
    ("segmentation", "Segmentation", "Splitting your audience into groups so you can send more relevant messages."),
    ("retargeting", "Retargeting", "Showing ads to people who already visited your site."),
]
OFFLINE_TOOLS = [
    ("canva", "Canva: quick designs", "Templates for posts, flyers and presentations. Check the current free plan limits."),
    ("photopea", "Photopea: free editor", "A Photoshop-style editor that runs in your browser. Check the current free plan limits."),
    ("google-search-console", "Google Search Console", "See which searches bring people to your site. Free from Google."),
    ("remove-bg", "Remove.bg", "Removes image backgrounds in seconds. Free tier is limited, check current terms."),
    ("google-analytics", "Google Analytics", "Understand where your visitors come from and what they read."),
    ("mailerlite-free", "A free email tool", "Start an email list with a free plan. Check the current free plan limits."),
]


def _sanitize(text: str, limit: int) -> str:
    text = re.sub(r"https?://\S+", "", text or "")
    text = re.sub(r"#\w+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    low = text.lower()
    if any(b in low for b in config.BANNED_WORDS):
        raise ValueError("banned phrase in generated text")
    return text[:limit].rstrip()


def _gemini(prompt: str):
    if config.OFFLINE or not config.GEMINI_API_KEY:
        return None
    for model in config.GEMINI_MODELS:
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": config.GEMINI_API_KEY, "Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"temperature": 0.9, "responseMimeType": "application/json"}},
                timeout=60)
            if r.status_code in (404, 400):
                continue  # model name not available for this key: try the next one
            r.raise_for_status()
            txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(txt)
        except Exception as e:
            print(f"gemini {model} failed: {e}")
    return None


SCHEMA = ('Return ONLY JSON: {"topic_key": "short-kebab-slug", "headline": "max 55 chars", '
          '"body": "max 150 chars, shown on the image", "caption": "max 350 chars, friendly, ends with a light '
          'call to action but NO link", "hashtags": ["5 to 7 lowercase words without #"]}')


def _prompt(kind: str, avoid: list, extra: str) -> str:
    return (f"{VOICE}\nTask: {extra}\nAvoid these topic_keys (already used): {avoid[-40:]}\n{SCHEMA}")


def _finish(kind: str, d: dict, link: str, link_label: str, extra: dict) -> dict:
    tags = [re.sub(r"[^a-z0-9]", "", str(t).lower()) for t in d.get("hashtags", [])]
    tags = [t for t in tags if t][:7] or ["digitalmarketing", "smallbusiness", "creators"]
    post = {
        "type": kind, "label": LABELS[kind],
        "topic_key": re.sub(r"[^a-z0-9-]", "", re.sub(r"\s+", "-", str(d.get("topic_key", "")).lower())[:60]) or kind,
        "headline": _sanitize(d["headline"], 70), "body": _sanitize(d["body"], 170),
        "caption": _sanitize(d["caption"], 400), "hashtags": tags,
        "link": link, "link_label": link_label,
    }
    post.update(extra)
    return post


def _pick_offline(pool, used):
    fresh = [p for p in pool if p[0] not in used] or pool
    return random.choice(fresh)


def make_post(kind: str, state: dict, catalog: list) -> dict:
    used = state.setdefault("used", {}).setdefault(kind, [])
    guides = {g["key"]: g for g in config.FREE_GUIDES}

    if kind in ("tip", "term", "tool"):
        guide = guides[config.TYPE_TO_GUIDE[kind]]
        instr = {
            "tip": "Write ONE practical email marketing tip for creators/small online sellers. headline = the tip as a short imperative, body = why/how in one sentence.",
            "term": "Explain ONE internet marketing term in plain English. headline = the term, body = a one-sentence definition, caption adds a tiny real-world example.",
            "tool": "Spotlight ONE well-known, still-active online marketing tool that is free or has a generous free plan. headline = tool name + what it does, body = one concrete use case, caption reminds readers to check the current free-plan limits.",
        }[kind]
        d = _gemini(_prompt(kind, used, instr))
        try:
            if d:
                post = _finish(kind, d, guide["url"], guide["title"], {"guide": guide["title"]})
                post["caption"] += f"\n\nWant the full list? Grab the free guide: {guide['title']}."
                return post
        except Exception as e:
            print("LLM output rejected:", e)
        pool = {"tip": OFFLINE_TIPS, "term": OFFLINE_TERMS, "tool": OFFLINE_TOOLS}[kind]
        key, head, body = _pick_offline(pool, used)
        d = {"topic_key": key, "headline": head, "body": body,
             "caption": f"{head}. {body} Save this for later.",
             "hashtags": ["emailmarketing" if kind == "tip" else "digitalmarketing", "smallbusiness", "creators", "marketingtips"]}
        post = _finish(kind, d, guide["url"], guide["title"], {"guide": guide["title"]})
        post["caption"] += f"\n\nWant the full list? Grab the free guide: {guide['title']}."
        return post

    if kind == "freebie":
        promo = state.setdefault("promoted", {})
        guide = sorted(config.FREE_GUIDES, key=lambda g: promo.get("guide:" + g["key"], 0))[0]
        promo["guide:" + guide["key"]] = promo.get("guide:" + guide["key"], 0) + 1
        d = _gemini(_prompt(kind, used,
                            f"Invite people to download this FREE guide: '{guide['title']}' - {guide['blurb']} "
                            "headline = benefit-led hook, body = what's inside in one sentence."))
        if not d:
            d = {"topic_key": "guide-" + guide["key"] + str(random.randint(1, 999)),
                 "headline": f"Free: {guide['title']}", "body": guide["blurb"],
                 "caption": f"{guide['title']} is free to download. {guide['blurb']}",
                 "hashtags": ["freedownload", "digitalmarketing", "smallbusiness", "creators"]}
        try:
            post = _finish(kind, d, guide["url"], guide["title"], {"guide": guide["title"]})
        except Exception:
            post = _finish(kind, {"topic_key": "guide-" + guide["key"], "headline": f"Free: {guide['title']}",
                                  "body": guide["blurb"], "caption": f"{guide['title']} is free to download.",
                                  "hashtags": ["freedownload", "digitalmarketing"]}, guide["url"], guide["title"], {"guide": guide["title"]})
        return post

    # product
    if not catalog:
        return make_post("freebie", state, catalog)
    promo = state.setdefault("promoted", {})
    prod = sorted(catalog, key=lambda p: promo.get("prod:" + p["slug"], 0))[0]
    promo["prod:" + prod["slug"]] = promo.get("prod:" + prod["slug"], 0) + 1
    price = fmt_price(prod.get("price", ""))
    facts = f"Title: {prod['title']}\nDescription: {prod.get('description', '')}\nPrice: {price}"
    d = _gemini(_prompt(kind, used,
                        "Write a benefit-led post for this digital product. Use ONLY the facts below.\n" + facts +
                        "\nheadline = the problem it solves as a hook, body = what you get (from the title), "
                        "caption = 2-3 short sentences" + (f" and mention it starts at {price}" if price else "") + "."))
    if not d:
        d = {"topic_key": prod["slug"][:50], "headline": prod["short"][:55],
             "body": (prod.get("description") or prod["title"])[:150],
             "caption": f"{prod['short']}" + (f" - from {price}." if price else ".") + " Instant digital download.",
             "hashtags": ["digitalproducts", "instantdownload", "creators", "smallbusiness"]}
    try:
        post = _finish(kind, d, prod["url"], prod["short"], {"product": prod["slug"], "price": price,
                                                              "cover": prod.get("image", "")})
    except Exception:
        post = _finish(kind, {"topic_key": prod["slug"][:50], "headline": prod["short"][:55],
                              "body": (prod.get("description") or prod["title"])[:150],
                              "caption": f"{prod['short']}. Instant digital download.",
                              "hashtags": ["digitalproducts", "instantdownload", "creators"]},
                       prod["url"], prod["short"], {"product": prod["slug"], "price": price, "cover": prod.get("image", "")})
    return post
