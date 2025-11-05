# Ultroid - UserBot
# Copyright (C) 2021-2025 TeamUltroid
#
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in
# <https://www.github.com/TeamUltroid/Ultroid/blob/main/LICENSE/>.
"""
✘ Commands Available -

• `{i}nhentai <digits/url>`
    Download manga from NHentai as PDF.
    - Use digits only (e.g., 177013) for single chapter
    - Use full URL for multi-chapter support (supports multiple sites)
"""

from . import get_help

__doc__ = get_help("help_nhentai")

import os
import re
from io import BytesIO

try:
    from PIL import Image
except ImportError:
    Image = None
    LOGS.info(f"{__file__}: PIL not Installed.")

from telethon.tl.types import DocumentAttributeFilename

from pyUltroid.fns.tools import create_tl_btn, get_msg_button

from . import LOGS, eor, get_string, ultroid_cmd
from ._inline import something


async def download_image(session, url):
    """Download image from URL."""
    try:
        import aiohttp
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                return await resp.read()
    except Exception as e:
        LOGS.error(f"Error downloading image: {e}")
    return None


async def create_pdf_from_images(images_data, title="NHentai"):
    """Create PDF from image data list."""
    if not images_data or not Image:
        return None
    
    try:
        pdf_images = []
        for img_data in images_data:
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
        pdf_buffer.name = "manga.pdf"
        return pdf_buffer
    except Exception as e:
        LOGS.error(f"Error creating PDF: {e}")
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
            "**Usage:** `.nhentai <digits>` or `.nhentai <url>`\n"
            "**Example:** `.nhentai 177013` or `.nhentai https://nhentai.net/g/177013/`"
        )
    
    # Determine if input is digits only or URL
    is_digits = re.match(r"^\d+$", input_text)
    
    xx = await eor(event, get_string("com_1"))
    
    # Prepare API endpoint
    if is_digits:
        api_url = f"https://weeb-api.vercel.app/nhentai/get?url=https://nhentai.net/g/{input_text}"
        is_multi = False
    else:
        api_url = f"https://weeb-api.vercel.app/nhentai-all?url={input_text}"
        is_multi = True
    
    # Fetch data
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get('Content-Type', '')
                    if 'application/json' in content_type:
                        data = await resp.json()
                    else:
                        text = await resp.text()
                        return await xx.edit(f"`Error: {text}`")
                else:
                    return await xx.edit(f"`API returned status code: {resp.status}`")
    except Exception as e:
        LOGS.error(f"API Error: {e}")
        return await xx.edit(f"`Failed to fetch data: {str(e)}`")
    
    if not data:
        return await xx.edit("`No data found.`")
    
    # Handle response
    if isinstance(data, list):
        if len(data) == 0:
            return await xx.edit("`No chapters found.`")
        chapter_data = data[0]
        total_chapters = len(data)
    else:
        chapter_data = data
        total_chapters = 1
    
    title = chapter_data.get("title", "NHentai Manga")
    images = chapter_data.get("images", [])
    
    if not images:
        return await xx.edit("`No images found.`")
    
    total_images = len(images)
    chapter_info = f" - Chapter 1/{total_chapters}" if total_chapters > 1 else ""
    await xx.edit(f"**Downloading {total_images} pages{chapter_info}...**\n`Progress: 0%`")
    
    # Download images
    images_data = []
    import aiohttp
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
                    f"**Downloading {total_images} pages{chapter_info}...**\n"
                    f"`Progress: {int(progress)}% ({idx}/{total_images})`"
                )
    
    if not images_data:
        return await xx.edit("`Failed to download any images.`")
    
    await xx.edit("`Creating PDF...`")
    pdf_buffer = await create_pdf_from_images(images_data, title)
    
    if not pdf_buffer:
        return await xx.edit("`Failed to create PDF.`")
    
    # Create filename
    safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
    if total_chapters > 1:
        filename = f"{safe_title[:50]} - Ch1.pdf" if len(safe_title) > 50 else f"{safe_title} - Ch1.pdf"
    else:
        filename = f"{safe_title[:50]}.pdf" if len(safe_title) > 50 else f"{safe_title}.pdf"
    
    # Prepare caption
    caption = f"**{title}**"
    if total_chapters > 1:
        caption += f"\n`Chapter 1/{total_chapters} - Pages: {len(images_data)}`"
    else:
        caption += f"\n`Pages: {len(images_data)}`"
    
    # Handle multi-chapter with buttons
    if total_chapters > 1:
        buttons = []
        for idx in range(2, total_chapters + 1):
            ch_data = data[idx - 1]
            ch_title = ch_data.get("title", f"Chapter {idx}")
            # Create button text and callback data
            button_text = f"Chapter {idx}"
            # Store the chapter data in a way that can be retrieved
            buttons.append([button_text, f"nhget_{idx}_{input_text}"])
        
        tl_buttons = create_tl_btn(buttons) if buttons else None
        
        await something(
            event,
            caption,
            pdf_buffer,
            tl_buttons
        )
        await xx.delete()
    else:
        # Single chapter - send normally
        await event.client.send_file(
            event.chat_id,
            pdf_buffer,
            attributes=[DocumentAttributeFilename(file_name=filename)],
            force_document=True,
            caption=caption,
            reply_to=event.reply_to_msg_id
        )
        await xx.delete()
        
