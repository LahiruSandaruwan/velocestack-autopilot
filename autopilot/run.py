"""CLI:  python -m autopilot.run generate | publish | site"""
import datetime as dt
import html
import json
import sys

from . import catalog, config, content, publish, render

STATE_FILE = config.DATA_DIR / "state.json"


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {"counter": 0, "used": {}, "promoted": {}, "history": [], "pending": None}


def save_state(state: dict):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    state["history"] = state.get("history", [])[-120:]
    STATE_FILE.write_text(json.dumps(state, indent=1))


# ------------------------------------------------------------------ generate
def cmd_generate():
    state = load_state()
    items = catalog.sync()
    kind = config.PATTERN[state.get("counter", 0) % len(config.PATTERN)]
    post = content.make_post(kind, state, items)
    state["counter"] = state.get("counter", 0) + 1
    state["used"].setdefault(post["type"], []).append(post["topic_key"])

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M")
    pid = f"{stamp}-{post['type']}"
    folder = config.POSTS_DIR / pid
    folder.mkdir(parents=True, exist_ok=True)

    render.render_card(post, (1080, 1350)).save(folder / "image.png", optimize=True)
    tall = folder / "tall.png"
    render.render_card(post, (1080, 1920)).save(tall, optimize=True)
    has_video = render.render_video(tall, folder / "reel.mp4")
    tall.unlink(missing_ok=True)
    post.update({"id": pid, "has_video": has_video, "created": stamp})
    (folder / "post.json").write_text(json.dumps(post, indent=1))
    state["pending"] = pid
    save_state(state)
    cmd_site(items)
    print(f"generated {pid}: {post['headline']}")


# ------------------------------------------------------------------ publish
def cmd_publish():
    state = load_state()
    pid = state.get("pending")
    if not pid:
        print("nothing pending")
        return 0
    folder = config.POSTS_DIR / pid
    post = json.loads((folder / "post.json").read_text())
    image, video = folder / "image.png", folder / "reel.mp4"
    results, errors = {}, {}
    rel = lambda p: f"{config.POSTS_DIR.name}/{pid}/{p}"

    tg_ready = bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)
    review_text = (f"[{post['label']}] {post['headline']}\n\n{post['caption']}\n\n{publish.link_for(post, 'telegram')}\n\n"
                   f"{publish.hashtags(post)}")

    if config.MODE != "auto":
        # Safe default: nothing goes public. You get the draft on Telegram and can post it yourself.
        if tg_ready:
            publish.telegram_send(config.TELEGRAM_CHAT_ID, image, "REVIEW MODE - not posted anywhere\n\n" + review_text,
                                  video if post.get("has_video") else None)
            results["telegram-review"] = "sent"
        else:
            print("review mode without Telegram: draft saved in the posts/ folder only")
        print("review:", results)
    else:
        plats = publish.enabled_platforms()
        if not plats:
            print("auto mode but no platform credentials set - nothing to do")
        img_url = publish.raw_url(rel("image.png")) if config.GITHUB_REPOSITORY else ""
        vid_url = publish.raw_url(rel("reel.mp4")) if config.GITHUB_REPOSITORY and post.get("has_video") else ""
        if plats and img_url and not publish.wait_for_url(img_url):
            errors["images"] = "image URL not reachable (is the repo public?)"
            plats = []
        for name, fn in [
            ("facebook", lambda: publish.facebook(post, img_url)),
            ("instagram", lambda: publish.instagram(post, image_url=img_url)),
            ("pinterest", lambda: publish.pinterest(post, img_url)),
        ]:
            if name not in " ".join(plats):
                continue
            try:
                results[name] = fn()
            except Exception as e:
                errors[name] = str(e)[:300]
        if config.IG_REELS and any(p.startswith("instagram") for p in plats) and vid_url:
            try:
                if publish.wait_for_url(vid_url):
                    results["instagram-reel"] = publish.instagram(post, video_url=vid_url)
            except Exception as e:
                errors["instagram-reel"] = str(e)[:300]
        if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHANNEL_ID:
            try:
                publish.telegram_send(config.TELEGRAM_CHANNEL_ID, image, review_text, None)
                results["telegram-channel"] = "sent"
            except Exception as e:
                errors["telegram-channel"] = str(e)[:300]
        if tg_ready:  # short log for you + the video so you can also post it to TikTok / Shorts by hand
            try:
                publish.telegram_send(config.TELEGRAM_CHAT_ID, image,
                                      f"POSTED: {post['headline']}\nok: {list(results)}\nerrors: {errors or 'none'}",
                                      video if post.get("has_video") else None)
            except Exception as e:
                print("telegram log failed:", e)
        print("posted:", results, "errors:", errors)

    state["history"].append({"id": pid, "type": post["type"], "headline": post["headline"], "mode": config.MODE,
                             "results": results, "errors": errors})
    state["pending"] = None
    save_state(state)
    return 0


# ------------------------------------------------------------------ link-in-bio site
def cmd_site(items=None):
    items = items if items is not None else catalog.sync()
    e = html.escape

    def card(title, sub, url, img=""):
        im = f'<img src="{e(img)}" alt="" loading="lazy">' if img else ""
        return f'<a class="card" href="{e(url)}" rel="noopener">{im}<span><b>{e(title)}</b><small>{e(sub)}</small></span></a>'

    free = "".join(card(g["title"], "Free download", g["url"] + "?utm_source=bio&utm_medium=organic&utm_campaign=linkinbio")
                   for g in config.FREE_GUIDES)
    shop = "".join(card(p["short"], ("From " + catalog.fmt_price(p.get("price", ""))) if p.get("price") else "Instant download",
                        p["url"] + "?utm_source=bio&utm_medium=organic&utm_campaign=linkinbio", p.get("image", ""))
                   for p in items)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(config.BRAND)} - links</title><meta name="description" content="Free marketing guides and instant-download digital products.">
<style>:root{{--ink:#1b1f3b;--acc:#5b5bd6;--soft:#f3f4fb}}*{{box-sizing:border-box}}body{{margin:0;font:16px/1.4 system-ui,sans-serif;background:var(--ink);color:#fff}}
main{{max-width:520px;margin:0 auto;padding:32px 16px 56px}}h1{{font-size:26px;margin:0 0 4px}}p.s{{color:#c9cbea;margin:0 0 24px}}
h2{{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#c9cbea;margin:28px 0 10px}}
.card{{display:flex;gap:12px;align-items:center;background:#fff;color:var(--ink);text-decoration:none;border-radius:14px;padding:12px;margin-bottom:10px}}
.card:hover{{outline:3px solid var(--acc)}}.card img{{width:56px;height:56px;object-fit:cover;border-radius:10px;flex:none}}
.card b{{display:block}}.card small{{color:#5c6078}}</style></head><body><main>
<h1>{e(config.BRAND)}</h1><p class="s">Free marketing guides + instant-download digital products.</p>
<h2>Free guides</h2>{free}<h2>Shop</h2>{shop}</main></body></html>"""
    config.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (config.DOCS_DIR / "index.html").write_text(page)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "generate":
        cmd_generate()
    elif cmd == "publish":
        sys.exit(cmd_publish())
    elif cmd == "site":
        cmd_site()
    else:
        print(__doc__)
        sys.exit(2)
