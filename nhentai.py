# Ultroid Addon: nhentai downloader
# Fixed PDF output + Progress updates (25-100%)
# Use: .nhentai <code>

import io
import requests
from fpdf import FPDF
from PIL import Image
from telethon.tl.custom import Button

from . import ultroid_cmd, HNDLR
from pyUltroid.fns.tools import cmd_regex_replace
from pyUltroid.dB._core import HELP, LIST

HELP["Official"]["nhentai"] = [
    f"**NHentai Downloader**\n\n"
    f"`{HNDLR}nhentai <code>` — Download doujin as PDF\n"
    f"`{HNDLR}nhentai-all <code>` — View chapters list\n"
]

NH_API = "https://nhentai.net/api/gallery/"


# ------------------------ PDF Converter --------------------------

def create_pdf(images, title="nhentai"):
    pdf = FPDF(unit="mm", format="A4")
    pdf.set_auto_page_break(0)
    
    total = len(images)
    done = 0
    
    for img_data in images:
        pdf.add_page()
        image = Image.open(io.BytesIO(img_data)).convert("RGB")
        w, h = image.size

        max_w, max_h = 210, 297  # A4 mm
        ratio = min(max_w / w, max_h / h)
        new_w, new_h = int(w * ratio), int(h * ratio)

        # Save to temp
        buf = io.BytesIO()
        image.resize((new_w, new_h)).save(buf, format="JPEG")
        buf.seek(0)

        pdf.image(buf, x=0, y=0, w=new_w, h=new_h)

        done += 1

    # return bytes instead of writing file
    return pdf.output(dest="S").encode("latin-1")


# ------------------------ Image Fetcher --------------------------

async def fetch_images(gid, send_status):
    meta = requests.get(NH_API + str(gid)).json()
    
    pages = meta["images"]["pages"]
    media_id = meta["media_id"]
    
    imgs = []
    total = len(pages)

    # notify in 4 chunks
    step_marks = { int(total*0.25): "25%", int(total*0.50): "50%", int(total*0.75): "75%" }

    for i, page in enumerate(pages):
        ext = { "j": "jpg", "p": "png", "g": "gif" }.get(page["t"], "jpg")
        url = f"https://i.nhentai.net/galleries/{media_id}/{i+1}.{ext}"

        img = requests.get(url).content
        imgs.append(img)

        if i in step_marks:
            await send_status(step_marks[i])

    return imgs, meta["title"]["english"]


# ------------------------ Commands --------------------------

@ultroid_cmd(pattern="nhentai-all ?(.*)")
async def nh_all(e):
    gid = e.pattern_match.group(1).strip()
    if not gid:
        return await e.eor("Give nhentai code.\nExample: `.nhentai-all 40000`")

    data = requests.get(NH_API + gid).json()
    title = data["title"]["english"]
    pages = len(data["images"]["pages"])

    if pages <= 1:
        return await e.eor(f"**{title}**\nOnly one chapter.\nUse `.nhentai {gid}`")

    await e.eor(
        f"**{title}**\nSelect to download:",
        buttons=[
            [Button.inline(f"Download ({pages} pages)", f"nhd_{gid}")]
        ]
    )


@ultroid_cmd(pattern="nhentai ?(.*)")
async def nhentai_cmd(e):
    gid = e.pattern_match.group(1).strip()
    if not gid:
        return await e.eor("Send NHentai code.\nExample: `.nhentai 40000`")

    msg = await e.eor(f"📥 Fetching `{gid}` metadata...")

    async def status(p):
        await msg.edit(f"📥 Downloading pages...\nProgress: **{p}**")

    try:
        imgs, title = await fetch_images(gid, status)
        await msg.edit(f"📚 Creating PDF...\nProcessing: **100%** ✅")

        pdf_bytes = create_pdf(imgs, title)

        await e.client.send_file(
            e.chat_id,
            io.BytesIO(pdf_bytes),
            file_name=f"{gid}.pdf",
            caption=f"✅ **{title}**\nNHentai `{gid}`"
        )

        await msg.delete()

    except Exception as er:
        await msg.edit(f"❌ Error\n`{er}`")


# ------------------ Inline handler for nhentai-all button ------------------

from telethon import events

@events.register(events.CallbackQuery(pattern=r"nhd_(.*)"))
async def _(event):
    gid = event.pattern_match.group(1)
    m = await event.edit(f"📥 Starting download `{gid}`")

    async def status(p):
        await m.edit(f"📥 Pages downloading: **{p}**")

    imgs, title = await fetch_images(gid, status)
    pdf_bytes = create_pdf(imgs, title)

    await event.client.send_file(
        event.chat_id,
        io.BytesIO(pdf_bytes),
        file_name=f"{gid}.pdf",
        caption=f"✅ **{title}**"
    )
    await m.delete()
