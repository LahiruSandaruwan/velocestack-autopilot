# VeloceStack Autopilot

Free, cloud-run organic marketing for the VeloceStack shop. Runs on **GitHub Actions**, so it keeps working when your laptop is off. Cost: **$0** (GitHub Actions free tier, Gemini free API, Telegram/Meta/Pinterest APIs, Pillow, ffmpeg).

## What it does (2 posts a day, 09:00 and 19:00 Sri Lanka time)

1. Reads your Fourthwall shop and finds **every public product** (new products are picked up automatically).
2. Picks the next post from a 14-slot weekly rotation: 7 education posts (email tip, marketing term, free tool), 3 free-guide posts (Gumroad lead magnets) and 4 product posts.
3. Writes the copy with the Gemini free tier (falls back to built-in templates if the API is unavailable or the text looks risky).
4. Renders a branded 1080x1350 image and a 7-second 9:16 video.
5. Sends it where you decide:
   - **review mode (default):** a draft goes only to your private Telegram chat. Nothing is posted publicly.
   - **auto mode:** posts to Facebook Page, Instagram, Pinterest (and an optional Telegram channel) for every platform that has credentials. You also get the video on Telegram to upload to TikTok / Shorts / Reels by hand.
6. Rebuilds a **link-in-bio page** (`docs/index.html`, free GitHub Pages) with your 3 free guides and all shop products. Every link carries UTM tags so you can see which platform sells.

Funnel: post -> free Gumroad guide -> thank-you PDF -> store. The `docs/` page is the link for every bio.

## Setup (about 20 minutes for review mode)

1. **Create a public GitHub repo** (public is required so Instagram/Facebook/Pinterest can fetch the images, and it makes Actions minutes unlimited) and push this folder:
   ```
   git init && git add -A && git commit -m "init" && git branch -M main
   git remote add origin https://github.com/<you>/velocestack-autopilot.git && git push -u origin main
   ```
2. **Settings > Pages**: Source "Deploy from a branch", branch `main`, folder `/docs`. Your bio link becomes `https://<you>.github.io/velocestack-autopilot/`.
3. **Gemini key (free):** create one at https://aistudio.google.com/apikey. Add it as secret `GEMINI_API_KEY` (Settings > Secrets and variables > Actions).
4. **Telegram (free):** talk to @BotFather, `/newbot`, copy the token -> secret `TELEGRAM_BOT_TOKEN`. Send any message to your new bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `chat.id` -> secret `TELEGRAM_CHAT_ID`.
5. **Test:** Actions tab > `autopilot` > Run workflow. Within a minute or two the draft arrives on Telegram. Run it a few times to look at the different post types.
6. From now on it runs by itself twice a day. In review mode you copy the image/caption to any platform you like.

## Going fully automatic (add platforms one at a time)

Set the repo **variable** `MODE` to `auto` only after you are happy with the drafts. A platform is skipped if its credentials are missing, so you can add them gradually. One platform failing never stops the others.

**Facebook Page + Instagram (Meta Graph API, free)**
- Instagram must be a Professional (Business/Creator) account linked to a Facebook Page you admin.
- At developers.facebook.com create an app (type Business). While the app is in Development mode you can post to Pages/accounts you own without app review.
- In Graph API Explorer create a user token with `pages_show_list, pages_manage_posts, pages_read_engagement, instagram_basic, instagram_content_publish`, exchange it for a long-lived token, then call `GET /me/accounts` and copy your Page's `access_token` (this Page token does not expire) -> secret `FB_PAGE_TOKEN`.
- Variables: `FB_PAGE_ID` (Page id) and `IG_USER_ID` (from `GET /<page-id>?fields=instagram_business_account`). Optional: `IG_REELS` = `1` to also publish the video as a Reel.

**Pinterest (free, needs API access approval)**
- Create an app at developers.pinterest.com. New apps start with Trial access, so pins may not be publicly visible until Standard access is approved. Check your first pin. Until then, pin from the Telegram drafts.
- Secret `PINTEREST_ACCESS_TOKEN` (scopes `boards:read, pins:read, pins:write`), variable `PINTEREST_BOARD_ID` (`GET /v5/boards`). Optional refresh: secrets `PINTEREST_REFRESH_TOKEN`, `PINTEREST_APP_ID`, `PINTEREST_APP_SECRET`.

**Telegram public channel (optional, instant):** create a channel, add your bot as admin, set variable `TELEGRAM_CHANNEL_ID` (e.g. `@yourchannel`).

**TikTok / YouTube Shorts:** their posting APIs need audits, so these stay semi-manual: the 9:16 video arrives on Telegram, you upload it (30 seconds).

## Safety rails built in

- Review mode is the default. Public posting only when you set `MODE=auto`.
- 2 posts/day maximum, random start delay, varied post types, topic memory so nothing repeats.
- No income promises: risky phrases are blocked and the post is replaced by a safe template.
- Only original content (your guides, your product names/prices/images from your own shop). Nothing copied from other people.
- Product facts come from your live shop page; the model is told not to invent features, numbers or discounts.

## Tuning

- Posting times: edit the two `cron` lines in `.github/workflows/autopilot.yml` (UTC).
- Mix of post types: edit `PATTERN` in `autopilot/config.py`.
- Add a new free guide: append to `FREE_GUIDES` in `autopilot/config.py`.
- Stop everything: Actions tab > autopilot > `...` > Disable workflow.

## Files

`autopilot/catalog.py` shop sync | `content.py` post writing + guardrails | `render.py` image/video | `publish.py` platform APIs | `run.py` CLI and bio page | `tests/smoke_test.py` offline test (`python tests/smoke_test.py`).

## Notes

- GitHub may pause scheduled workflows in public repos after 60 days without activity. Daily commits from the bot normally prevent this. If it is ever paused, click "Enable workflow".
- Check the numbers weekly: Fourthwall analytics + Gumroad audience + the UTM tags (`utm_source=pinterest|facebook|bio|telegram`).
- API model names and platform rules change over time. If a platform starts returning errors, the Telegram log message shows the reason.
