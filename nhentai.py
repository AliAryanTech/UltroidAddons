# Ultroid - UserBot
# Copyright (C) 2021-2025 TeamUltroid
#
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in
# <https://www.github.com/TeamUltroid/Ultroid/blob/main/LICENSE/>.
"""
✘ Commands Available -

• `{i}nhentai <digits/url>`
    Download manga from NHentai.
    - Use digits only (e.g., 177013) for single chapter
    - Use full URL for multi-chapter support
    Sends PDF file with inline navigation for multiple chapters.
"""

import os
import re
from io import BytesIO

try:
    from PIL import Image
except ImportError:
    Image = None

import aiohttp

from . import LOGS, eor, get_string, ultroid_cmd
from ._inline import something


async def download_image(session, url):
    """Download image from URL."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                return await resp.read()
    except Exception as e:
        LOGS.error(f"Error downloading image: {e}")
    return None


async def create_pdf_from_images(images_data, title="NHentai"):
    """Create PDF from image data list."""
    if not images_data:
        return None
    
    try:
        pdf_images = []
        for idx, img_data in enumerate(images_data):
            if img_data:
                img = Image.open(BytesIO(img_data))
                if img.mode == "RGBA":
                    img = img.convert("RGB")
                elif img.mode != "RGB":
                    img = img.convert("RGB")
                pdf_images.append(img)
        
        if not pdf_images:
            return None
        
        pdf_buffer = BytesIO()
        pdf_images[0].save(
            pdf_buffer,
            "PDF",
            resolution=100.0,
            save_all=True,
            append_images=pdf_images[1:] if len(pdf_images) > 1 else []
        )
        pdf_buffer.seek(0)
        return pdf_buffer
    except Exception as e:
        LOGS.error(f"Error creating PDF: {e}")
        return None


async def fetch_nhentai_data(url, is_multi=False):
    """Fetch data from NHentai API."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        LOGS.error(f"Error fetching NHentai data: {e}")
    return None


@ultroid_cmd(pattern="nhentai( (.*)|$)")
async def nhentai_download(event):
    """Download manga from NHentai."""
    if not Image:
        return await eor(event, "`PIL is not installed. Cannot create PDF.`")
    
    input_text = event.pattern_match.group(1).strip()
    if not input_text:
        return await eor(
            event,
            "**Usage:** `.nhentai <digits>` or `.nhentai <nhentai_url>`\n"
            "**Example:** `.nhentai 177013` or `.nhentai https://nhentai.net/g/177013/`"
        )
    
    # Determine if input is digits only or full URL
    is_digits = re.match(r"^\d+$", input_text)
    is_url = "nhentai.net/g/" in input_text
    
    if not is_digits and not is_url:
        return await eor(event, "`Invalid input. Provide NHentai digits or full URL.`")
    
    xx = await eor(event, get_string("com_1"))
    
    # Prepare API endpoint
    if is_digits:
        api_url = f"https://weeb-api.vercel.app/nhentai/get?url=https://nhentai.net/g/{input_text}"
        is_multi = False
    else:
        api_url = f"https://weeb-api.vercel.app/nhentai-all?url={input_text}"
        is_multi = True
    
    # Fetch data
    data = await fetch_nhentai_data(api_url, is_multi)
    if not data:
        return await xx.edit("`Failed to fetch data from NHentai API.`")
    
    # Handle single chapter
    if not is_multi or not isinstance(data, list) or len(data) == 1:
        chapter_data = data[0] if isinstance(data, list) else data
        title = chapter_data.get("title", "NHentai")
        images = chapter_data.get("images", [])
        
        if not images:
            return await xx.edit("`No images found.`")
        
        total_images = len(images)
        await xx.edit(f"**Downloading {total_images} pages...**\n`Progress: 0%`")
        
        images_data = []
        async with aiohttp.ClientSession() as session:
            for idx, img_url in enumerate(images, 1):
                img_data = await download_image(session, img_url)
                if img_data:
                    images_data.append(img_data)
                
                # Update progress at 20%, 40%, 60%, 80%, 100%
                progress = (idx / total_images) * 100
                if idx == int(total_images * 0.2) or idx == int(total_images * 0.4) or \
                   idx == int(total_images * 0.6) or idx == int(total_images * 0.8) or \
                   idx == total_images:
                    await xx.edit(
                        f"**Downloading {total_images} pages...**\n"
                        f"`Progress: {int(progress)}% ({idx}/{total_images})`"
                    )
        
        await xx.edit("`Creating PDF...`")
        pdf_buffer = await create_pdf_from_images(images_data, title)
        
        if not pdf_buffer:
            return await xx.edit("`Failed to create PDF.`")
        
        filename = f"{title[:50]}.pdf" if len(title) > 50 else f"{title}.pdf"
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        
        await event.client.send_file(
            event.chat_id,
            pdf_buffer,
            attributes=[],
            force_document=True,
            caption=f"**{title}**\n`Pages: {len(images_data)}`",
            reply_to=event.reply_to_msg_id
        )
        await xx.delete()
    
    # Handle multiple chapters
    else:
        first_chapter = data[0]
        title = first_chapter.get("title", "NHentai")
        images = first_chapter.get("images", [])
        
        if not images:
            return await xx.edit("`No images found in first chapter.`")
        
        total_images = len(images)
        await xx.edit(f"**Downloading Chapter 1 ({total_images} pages)...**\n`Progress: 0%`")
        
        images_data = []
        async with aiohttp.ClientSession() as session:
            for idx, img_url in enumerate(images, 1):
                img_data = await download_image(session, img_url)
                if img_data:
                    images_data.append(img_data)
                
                progress = (idx / total_images) * 100
                if idx == int(total_images * 0.2) or idx == int(total_images * 0.4) or \
                   idx == int(total_images * 0.6) or idx == int(total_images * 0.8) or \
                   idx == total_images:
                    await xx.edit(
                        f"**Downloading Chapter 1 ({total_images} pages)...**\n"
                        f"`Progress: {int(progress)}% ({idx}/{total_images})`"
                    )
        
        await xx.edit("`Creating PDF...`")
        pdf_buffer = await create_pdf_from_images(images_data, title)
        
        if not pdf_buffer:
            return await xx.edit("`Failed to create PDF.`")
        
        filename = f"{title[:50]} - Ch1.pdf" if len(title) > 50 else f"{title} - Ch1.pdf"
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        
        # Create inline buttons for other chapters
        buttons = []
        for idx, chapter in enumerate(data[1:], 2):
            ch_title = chapter.get("title", f"Chapter {idx}")
            buttons.append([f"Chapter {idx}", f"nhget_{idx-1}_{input_text}"])
        
        from pyUltroid.fns.tools import create_tl_btn
        tl_buttons = create_tl_btn(buttons) if buttons else None
        
        caption = f"**{title}**\n`Chapter 1 - Pages: {len(images_data)}`\n\n`Total Chapters: {len(data)}`"
        
        await something(
            event,
            caption,
            pdf_buffer,
            tl_buttons
        )
        await xx.delete()
