# Ultroid - UserBot
#
# This file is a part of < https://github.com/TeamUltroid/UltroidAddons/>

"""
Fetch manga from NHentai and similar sites

Commands:
• `{i}nhentai <digits/url>`
    Download manga from NHentai as PDF.
    - Use digits only (e.g., 177013) for single chapter
    - Use full URL for multi-chapter support
    Supports: nhentai.net, hentaifox.com, simply-hentai.com, and more
"""

import os
import re
from io import BytesIO

try:
    from PIL import Image
except ImportError:
    Image = None

from . import ultroid_cmd, async_searcher, eor, get_string, LOGS


async def download_image(url):
    """Download image from URL."""
    try:
        img_data = await async_searcher(url, re_content=True)
        return img_data
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
        pdf_buffer.name = f"{title[:50]}.pdf" if len(title) > 50 else f"{title}.pdf"
        pdf_buffer.name = re.sub(r'[<>:"/\\|?*]', '', pdf_buffer.name)
        
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
            "**Example:** `.nhentai 177013` or `.nhentai https://nhentai.net/g/177013/`\n"
            "**Supported sites:** nhentai.net, hentaifox.com, simply-hentai.com, and more"
        )
    
    # Determine if input is digits only or full URL
    is_digits = re.match(r"^\d+$", input_text)
    
    xx = await eor(event, get_string("com_1"))
    
    # Prepare API endpoint
    if is_digits:
        api_url = f"https://weeb-api.vercel.app/nhentai/get?url=https://nhentai.net/g/{input_text}"
    else:
        api_url = f"https://weeb-api.vercel.app/nhentai-all?url={input_text}"
    
    # Fetch data
    try:
        data = await async_searcher(api_url, re_json=True)
    except Exception as e:
        LOGS.error(f"API Error: {e}")
        return await xx.edit("`Failed to fetch data from API.`")
    
    if not data:
        return await xx.edit("`No data found.`")
    
    # Check if API returned error message (unsupported URL)
    if isinstance(data, str):
        return await xx.edit(f"`{data}`")
    
    # Handle response (single or multi chapter)
    if isinstance(data, list):
        if len(data) == 0:
            return await xx.edit("`No chapters found.`")
        # For multi-chapter, only download first one
        chapter_data = data[0]
        total_chapters = len(data)
        chapter_info = f" (Chapter 1/{total_chapters})" if total_chapters > 1 else ""
        is_multi = total_chapters > 1
    else:
        chapter_data = data
        chapter_info = ""
        is_multi = False
    
    title = chapter_data.get("title", "NHentai")
    images = chapter_data.get("images", [])
    
    if not images:
        return await xx.edit("`No images found.`")
    
    total_images = len(images)
    await xx.edit(f"**Downloading {total_images} pages{chapter_info}...**\n`Progress: 0%`")
    
    images_data = []
    for idx, img_url in enumerate(images, 1):
        img_data = await download_image(img_url)
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
        return await xx.edit("`Failed to download images.`")
    
    await xx.edit("`Creating PDF...`")
    pdf_buffer = await create_pdf_from_images(images_data, title)
    
    if not pdf_buffer:
        return await xx.edit("`Failed to create PDF.`")
    
    # Prepare caption
    caption = f"**{title}**{chapter_info}\n`Pages: {len(images_data)}`"
    
    # Send file with proper attributes
    if is_multi:
        # For multi-chapter, send with button message
        caption += f"\n\n📚 **Total Chapters:** {total_chapters}"
        caption += "\n_Use the same command with full URL to access other chapters_"
        
        # Send the PDF
        await event.client.send_file(
            event.chat_id,
            pdf_buffer,
            force_document=True,
            caption=caption,
            reply_to=event.reply_to_msg_id
        )
    else:
        # Single chapter - just send the file
        await event.client.send_file(
            event.chat_id,
            pdf_buffer,
            force_document=True,
            caption=caption,
            reply_to=event.reply_to_msg_id
        )
    
    await xx.delete()
    
