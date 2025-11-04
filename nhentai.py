# nhentai.py — Clean rebuild for Ultroid
# Works with Weeb API: https://weeb-api.vercel.app
# Requires: pillow, aiohttp

import io
import asyncio
import aiohttp
import re
from PIL import Image
from telethon.tl.custom import Button

from . import (
    ultroid_cmd,
    eor,
    LOGS,
    callback,
)

### API
API_ALL = "https://weeb-api.vercel.app/nhentai-all?url={}"
API_GET = "https://weeb-api.vercel.app/nhentai/get?url=https://nhentai.net/g/{}"

SUPPORTED = {
    "nhentai.com","nhentai.net","hentai2read.com","hentaiforce.net",
    "www2.hentai2.net","hentaifox.com","hdporncomics.com","allporncomic.com",
    "allporncomic.io","milftoon.xxx"
}

NH_SESSION = {}


### Helpers
def _resolve_api(q: str):
    q = q.strip()
    if q.isdigit():
        return API_GET.format(q)
    for domain in SUPPORTED:
        if domain in q:
            return API_ALL.format(q)
    return None


async def _get_json(sess, url):
    try:
        async with sess.get(url, timeout=40) as r:
            r.raise_for_status()
            return await r.json()
    except Exception:
        LOGS.exception("JSON fetch failed: %s", url)
        return None


async def _get_img(sess, url):
    try:
        async with sess.get(url, timeout=90) as r:
            r.raise_for_status()
            return await r.read()
    except Exception:
        LOGS.exception("Image dl failed: %s", url)
        return None


def _make_pdf(img_bytes, title):
    if not img_bytes:
        return None

    images = []
    for b in img_bytes:
        try:
            im = Image.open(io.BytesIO(b))
            if im.mode != "RGB":
                im = im.convert("RGB")
            images.append(im)
        except:
            pass

    if not images:
        return None

    safe = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_"))[:120] or "file"
    bio = io.BytesIO()
    bio.name = f"{safe}.pdf"

    try:
        images[0].save(bio, "PDF", save_all=True, append_images=images[1:])
        bio.seek(0)
        return bio
    except:
        LOGS.exception("PDF failed")
        return None


async def _download_with_progress(msg, sess, urls):
    total = len(urls)
    sem = asyncio.Semaphore(8)

    chunks = 5  # 20/40/60/80/100
    marks = [(i * (100 // chunks)) for i in range(1, chunks + 1)]
    last_mark = 0

    async def _dl(url, idx):
        async with sem:
            return idx, await _get_img(sess, url)

    tasks = [asyncio.create_task(_dl(url, i)) for i, url in enumerate(urls)]
    results = []

    for i, t in enumerate(asyncio.as_completed(tasks), start=1):
        res = await t
        if res and res[1]:
            results.append(res)

        pct = (i / total) * 100
        for m in marks:
            if pct >= m > last_mark:
                last_mark = m
                await msg.edit(f"`Downloading… {m}%`")
                break

    results.sort(key=lambda x: x[0])
    return [b for _, b in results]


### Command
@ultroid_cmd(pattern="nhentai ?(.*)")
async def _(e):
    q = e.pattern_match.group(1).strip()
    if not q:
        return await eor(e, "`Usage: .nhentai <id|url>`")

    api = _resolve_api(q)
    if not api:
        return await eor(e, "`Unsupported link or code.`")

    msg = await eor(e, "`Fetching...`")

    async with aiohttp.ClientSession() as sess:
        data = await _get_json(sess, api)
        if not data:
            return await msg.edit("`API failed.`")

        title = data.get("title") or "untitled"
        imgs = data.get("images") or []
        chapters = data.get("chapterList")

        # No chapterList → send single PDF
        if not chapters:
            if not imgs:
                return await msg.edit("`No images found.``")

            img_bytes = await _download_with_progress(msg, sess, imgs)
            if not img_bytes:
                return await msg.edit("`Images failed.`")

            await msg.edit("`Building PDF...`")
            pdf = _make_pdf(img_bytes, title)
            if not pdf:
                return await msg.edit("`PDF error.`")

            await e.client.send_file(e.chat_id, pdf, caption=title, force_document=True, reply_to=e.reply_to_msg_id)
            return await msg.delete()

        # Single chapter behavior → auto download
        if len(chapters) == 1:
            if imgs:
                img_bytes = await _download_with_progress(msg, sess, imgs)
                if not img_bytes:
                    return await msg.edit("`Images failed.`")

                await msg.edit("`Building PDF...`")
                pdf = _make_pdf(img_bytes, title)
                await e.client.send_file(e.chat_id, pdf, caption=title, force_document=True, reply_to=e.reply_to_msg_id)
                return await msg.delete()

            ch = chapters[0]
            link = ch.get("link")
            if not link:
                return await msg.edit("`Invalid chapter link.`")

            await msg.edit("`Fetching chapter...`")
            d = await _get_json(sess, API_ALL.format(link))
            imgs = d.get("images") or []
            if not imgs:
                return await msg.edit("`No pages.`")

            img_bytes = await _download_with_progress(msg, sess, imgs)
            await msg.edit("`Building PDF...`")
            pdf = _make_pdf(img_bytes, ch.get("title") or title)
            await e.client.send_file(e.chat_id, pdf, caption=ch.get("title"), force_document=True, reply_to=e.reply_to_msg_id)
            return await msg.delete()

        # Multi chapter → send full gallery then buttons
        if imgs:
            img_bytes = await _download_with_progress(msg, sess, imgs)
            if img_bytes:
                await msg.edit("`Building Full PDF...`")
                pdf = _make_pdf(img_bytes, title)
                if pdf:
                    await e.client.send_file(e.chat_id, pdf, caption=f"{title} (full)", force_document=True, reply_to=e.reply_to_msg_id)

        NH_SESSION[e.sender_id] = {"chapters": chapters}

        buttons = []
        for i, ch in enumerate(chapters):
            nm = ch.get("title") or f"Chapter {i+1}"
            pg = f" ({ch.get('pages')}p)" if isinstance(ch.get("pages"), int) else ""
            buttons.append([Button.inline(f"{nm}{pg}"[:64], data=f"nhc|{e.sender_id}|{i}")])

        return await msg.edit(f"**{title}**\nSelect chapter:", buttons=buttons)


### Callback
@callback(re.compile(r"nhc\|(\d+)\|(\d+)"), owner=False)
async def _(e):
    orig, idx = map(int, e.pattern_match.groups())
    if e.sender_id != orig:
        return await e.answer("Not your request.", alert=True)

    s = NH_SESSION.get(orig)
    if not s:
        return await e.answer("Session expired.", alert=True)

    chs = s["chapters"]
    if idx >= len(chs):
        return await e.answer("Invalid.", alert=True)

    ch = chs[idx]
    link = ch.get("link")
    title = ch.get("title") or f"chapter-{idx+1}"

    await e.edit(f"`Fetching {title}...`")
    async with aiohttp.ClientSession() as sess:
        d = await _get_json(sess, API_ALL.format(link))
        imgs = d.get("images") or []

        img_bytes = await _download_with_progress(e, sess, imgs)
        await e.edit("`Building PDF...`")
        pdf = _make_pdf(img_bytes, title)

        await e.client.send_file(e.chat_id, pdf, caption=title, force_document=True)
        await e.delete()

    NH_SESSION.pop(orig, None)
