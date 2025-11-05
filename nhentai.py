# Ultroid addon: NHentai downloader
# Dumb bots break, smart bots read instructions.

import os
import io
import requests
from telethon import Button
from PIL import Image
from fpdf import FPDF
from . import ultroid_cmd

API_ALL = "https://weeb-api.vercel.app/nhentai-all?url="
API_GET = "https://weeb-api.vercel.app/nhentai/get?url=https://nhentai.net/g/{}"


def build_pdf(images, title):
    pdf = FPDF(unit="pt", format="A4")
    for img_bytes in images:
        img = Image.open(io.BytesIO(img_bytes))
        w, h = img.size

        pdf.add_page()
        # resize keeping ratio to page width
        ratio = 595 / w
        nh = h * ratio
        img = img.resize((595, int(nh)))
        temp = io.BytesIO()
        img.save(temp, format="JPEG")
        temp.seek(0)
        pdf.image(temp, 0, 0, 595, int(nh))
    
    memory_file = io.BytesIO()
    pdf.output(memory_file, "F")
    memory_file.seek(0)
    return memory_file


async def fetch_images(url):
    r = requests.get(url).json()
    title = r.get("title")
    chapters = r.get("chapters")
    images = []

    if chapters and len(chapters) > 1:
        return "MULTI", title, chapters

    # single chapter
    for img in r.get("images", []):
        images.append(requests.get(img).content)

    return "SINGLE", title, images


async def dl_chapter(chapter):
    imgs = []
    for img in chapter.get("images", []):
        imgs.append(requests.get(img).content)
    return imgs


def split_progress(total, stage):
    return f"📥 Downloading… {int((stage/5)*100)}%"


@ultroid_cmd(pattern="nhentai ?(.*)")
async def nhentai_cmd(event):
    q = event.pattern_match.group(1).strip()
    if not q:
        return await event.eor("Give code or NHentai link.")

    # Detect if input is link or code
    if q.isdigit():
        url = API_GET.format(q)
    elif "nhentai.net" in q:
        url = API_ALL + q
    else:
        return await event.eor("Invalid input.")

    msg = await event.eor("Fetching info…")

    mode, title, data = await fetch_images(url)

    # MULTI CHAPTER HANDLING
    if mode == "MULTI":
        buttons = []
        for i, chap in enumerate(data):
            chap_id = chap.get("id", i)
            buttons.append(
                [Button.inline(f"📄 Chapter {i+1}", f"nhchap_{chap_id}")]
            )

        # Download first chapter PDF
        ch_imgs = await dl_chapter(data[0])
        pdf = build_pdf(ch_imgs, title)

        await msg.edit(f"✅ **{title}**\nMultiple chapters found.\nSending first chapter...")
        await event.client.send_file(event.chat_id, pdf, caption=f"**{title} — Ch 1**", force_document=True, buttons=buttons)
        return

    # SINGLE CHAPTER
    # data = images list
    imgs = data
    total = len(imgs)
    batch = max(1, total // 5)

    downloaded = []
    for i, img in enumerate(imgs):
        downloaded.append(img)
        if (i+1) % batch == 0 or i+1 == total:
            stage = min(5, len(downloaded) // batch)
            await msg.edit(split_progress(total, stage))

    pdf = build_pdf(downloaded, title)

    await msg.edit("✅ 100% Completed. Sending file…")
    await event.client.send_file(event.chat_id, pdf, caption=f"**{title}**", force_document=True)


# Callback for chapters
@ultroid_cmd(incoming=True)
async def cb_handler(event):
    if not event.data.startswith(b"nhchap_"):
        return

    chap_id = event.data.decode().split("_",1)[1]
    await event.answer("Processing…")

    # fetch chapter list again (user originally sent URL)
    original = (await event.get_reply_message()).message
    link = ''.join([x for x in original.split() if "nhentai.net" in x])

    mode, title, data = await fetch_images(API_ALL + link)

    chapter = next((c for c in data if str(c.get("id")) == chap_id), None)
    if not chapter:
        return await event.edit("Chapter not found.")

    imgs = await dl_chapter(chapter)

    msg = await event.respond(f"📥 Downloading chapter {chap_id}…")
    total = len(imgs)
    batch = max(1, total//5)

    downloaded = []
    for i, img in enumerate(imgs):
        downloaded.append(img)
        if (i+1) % batch == 0 or i+1 == total:
            stage = min(5, len(downloaded)//batch)
            await msg.edit(split_progress(total, stage))

    pdf = build_pdf(downloaded, title)
    await event.client.send_file(event.chat_id, pdf, caption=f"**{title} — Chapter**", force_document=True)
