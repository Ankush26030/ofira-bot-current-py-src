"""
Canvas Music Card Generator
Generates a stunning music card image using Pillow with a custom
blurry background image, circular thumbnail, wavy progress bar,
and stylish text with drop shadows.
"""
import io
import math
import os
import random
import discord
import aiohttp
import wavelink
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from utils.formatters import format_duration

# ── Colour Constants ────────────────────────────────────────────
ACCENT_PURPLE  = (120, 60, 220)
ACCENT_BLUE    = (40, 120, 255)
ACCENT_PINK    = (200, 60, 180)
ACCENT_CYAN    = (60, 200, 240)
TEXT_WHITE     = (255, 255, 255)
TEXT_GRAY      = (200, 200, 220)
TEXT_DIM       = (160, 150, 190)
SHADOW_COLOR   = (0, 0, 0, 120)
BAR_BG         = (255, 255, 255, 35)
BADGE_BG       = (255, 255, 255, 30)

# ── Dimensions ──────────────────────────────────────────────────
CARD_W, CARD_H = 900, 300
THUMB_SIZE     = 180
PADDING        = 28
CORNER_RADIUS  = 22
BAR_H          = 6
WAVE_AMP       = 3        # Amplitude of the wavy progress bar
WAVE_FREQ      = 0.06     # Frequency of the sine wave

# ── Background image path ──────────────────────────────────────
_BG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "music.png")
_bg_cache: Image.Image | None = None


def _load_bg_image(w: int, h: int) -> Image.Image:
    """Load, scale, blur, and darken the background image. Cached after first call."""
    global _bg_cache
    if _bg_cache is not None and _bg_cache.size == (w, h):
        return _bg_cache.copy()

    try:
        bg = Image.open(_BG_PATH).convert("RGBA")
    except Exception:
        # Fallback: solid dark card if image not found
        bg = Image.new("RGBA", (w, h), (15, 10, 30, 255))
        _bg_cache = bg
        return bg.copy()

    # Scale to cover
    art_ratio = bg.width / bg.height
    card_ratio = w / h
    if art_ratio > card_ratio:
        new_h = h
        new_w = int(h * art_ratio)
    else:
        new_w = w
        new_h = int(w / art_ratio)
    bg = bg.resize((new_w, new_h), Image.LANCZOS)

    # Center-crop
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    bg = bg.crop((left, top, left + w, top + h))

    # Heavy Gaussian blur
    bg = bg.filter(ImageFilter.GaussianBlur(radius=10))

    # Dark overlay for readability
    dark = Image.new("RGBA", (w, h), (0, 0, 0, 150))
    bg = Image.alpha_composite(bg, dark)

    # Subtle purple tint
    tint = Image.new("RGBA", (w, h), ACCENT_PURPLE + (20,))
    bg = Image.alpha_composite(bg, tint)

    _bg_cache = bg
    return bg.copy()


def _round_corner_mask(size: tuple[int, int], radius: int) -> Image.Image:
    """Create a rounded-rectangle alpha mask."""
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (size[0] - 1, size[1] - 1)], radius=radius, fill=255)
    return mask


def _circle_mask(size: int) -> Image.Image:
    """Create a circular alpha mask."""
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([(0, 0), (size - 1, size - 1)], fill=255)
    return mask


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a font, preferring Segoe UI for a clean modern look."""
    try:
        font_name = "segoeuib.ttf" if bold else "segoeui.ttf"
        return ImageFont.truetype(font_name, size)
    except OSError:
        try:
            font_name = "arialbd.ttf" if bold else "arial.ttf"
            return ImageFont.truetype(font_name, size)
        except OSError:
            return ImageFont.load_default()


def _truncate_text(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    """Truncate text with ellipsis if it exceeds max_width."""
    if not text:
        return ""
    bbox = draw.textbbox((0, 0), text, font=font)
    if bbox[2] - bbox[0] <= max_width:
        return text
    while len(text) > 1:
        text = text[:-1]
        test = text.rstrip() + "…"
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return test
    return "…"


def _draw_text_shadow(draw: ImageDraw.Draw, pos: tuple, text: str, font, fill, shadow_offset: int = 2):
    """Draw text with a drop shadow for depth."""
    sx, sy = pos[0] + shadow_offset, pos[1] + shadow_offset
    draw.text((sx, sy), text, fill=SHADOW_COLOR, font=font)
    draw.text(pos, text, fill=fill, font=font)


def _draw_wavy_progress_bar(
    draw: ImageDraw.Draw,
    card: Image.Image,
    x: int, y: int, width: int,
    position: int, duration: int,
):
    """Draw a straight progress bar with scalloped (wavy) edges and gradient."""
    mid_y = y + BAR_H // 2
    scallop_amp = 3       # Height of the scallop bumps
    scallop_freq = 0.12   # How tight the scallops are

    # ── Background bar with scalloped edges (dim) ────────────────
    for px in range(width):
        top_edge = int(mid_y - BAR_H // 2 - scallop_amp * abs(math.sin(px * scallop_freq)))
        bot_edge = int(mid_y + BAR_H // 2 + scallop_amp * abs(math.sin(px * scallop_freq)))
        for py in range(top_edge, bot_edge + 1):
            try:
                card.putpixel((x + px, py), (255, 255, 255, 25))
            except (IndexError, ValueError):
                pass

    # ── Filled portion with scalloped edges (gradient) ───────────
    if duration > 0:
        pct = min(position / duration, 1.0)
        fill_w = max(int(width * pct), 4)

        for px in range(fill_w):
            t = px / max(fill_w, 1)
            r = int(ACCENT_PURPLE[0] + (ACCENT_CYAN[0] - ACCENT_PURPLE[0]) * t)
            g = int(ACCENT_PURPLE[1] + (ACCENT_CYAN[1] - ACCENT_PURPLE[1]) * t)
            b = int(ACCENT_PURPLE[2] + (ACCENT_CYAN[2] - ACCENT_PURPLE[2]) * t)

            top_edge = int(mid_y - BAR_H // 2 - scallop_amp * abs(math.sin(px * scallop_freq)))
            bot_edge = int(mid_y + BAR_H // 2 + scallop_amp * abs(math.sin(px * scallop_freq)))
            for py in range(top_edge, bot_edge + 1):
                try:
                    card.putpixel((x + px, py), (r, g, b, 255))
                except (IndexError, ValueError):
                    pass

        # ── Glowing dot at current position ──────────────────────
        dot_cx = x + fill_w - 1
        dot_cy = mid_y

        # Outer glow
        glow = Image.new("RGBA", card.size, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        for gr in range(14, 0, -1):
            alpha = int(35 * (gr / 14))
            glow_draw.ellipse(
                [(dot_cx - gr, dot_cy - gr), (dot_cx + gr, dot_cy + gr)],
                fill=(ACCENT_CYAN[0], ACCENT_CYAN[1], ACCENT_CYAN[2], alpha),
            )
        card_copy = Image.alpha_composite(card, glow)
        card.paste(card_copy)

        # Solid dot
        dot_r = 7
        draw_fresh = ImageDraw.Draw(card)
        draw_fresh.ellipse(
            [(dot_cx - dot_r, dot_cy - dot_r), (dot_cx + dot_r, dot_cy + dot_r)],
            fill=TEXT_WHITE,
        )
        # Inner purple dot
        inner_r = 3
        draw_fresh.ellipse(
            [(dot_cx - inner_r, dot_cy - inner_r), (dot_cx + inner_r, dot_cy + inner_r)],
            fill=ACCENT_PURPLE,
        )


async def _fetch_thumbnail(url: str) -> Image.Image | None:
    """Download a thumbnail from URL."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        pass
    return None


def _get_source_label(track: wavelink.Playable) -> str:
    """Get a human-readable source label."""
    source = getattr(track, "source", "").lower()
    labels = {
        "youtube": "YouTube",
        "spotify": "Spotify",
        "soundcloud": "SoundCloud",
        "twitch": "Twitch",
        "bandcamp": "Bandcamp",
    }
    return labels.get(source, "Music")


def _draw_source_badge(draw: ImageDraw.Draw, x: int, y: int, text: str, font):
    """Draw a pill-shaped badge for the source label."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pad_x, pad_y = 12, 6
    pill_w = tw + pad_x * 2
    pill_h = th + pad_y * 2
    draw.rounded_rectangle(
        [(x, y), (x + pill_w, y + pill_h)],
        radius=pill_h // 2,
        fill=BADGE_BG,
    )
    # Center text vertically using middle anchor
    text_y = y + pill_h // 2
    draw.text((x + pad_x, text_y), text, fill=ACCENT_CYAN, font=font, anchor="lm")
    return pill_w


async def generate_music_card(
    track: wavelink.Playable,
    position: int = 0,
    requester: discord.Member | discord.User | None = None,
) -> discord.File:
    """
    Generate a music card image and return it as a discord.File.

    Parameters
    ----------
    track : wavelink.Playable
        The currently playing track.
    position : int
        Current playback position in milliseconds.
    requester : discord.Member | discord.User | None
        The user who requested the track.

    Returns
    -------
    discord.File
        The generated card as 'music_card.png'.
    """
    # ── Safety: if track is None, create a minimal stub ────────
    if track is None:
        class _Stub:
            title = "Unknown"
            author = "Unknown Artist"
            artwork = None
            thumbnail = None
            source = ""
            length = 0
            identifier = ""
        track = _Stub()

    # ── Base card with blurry background image ───────────────────
    card = _load_bg_image(CARD_W, CARD_H)
    draw = ImageDraw.Draw(card)

    # ── Circular Thumbnail ──────────────────────────────────────
    thumb_x = PADDING + 10
    thumb_cy = CARD_H // 2
    thumb_y = thumb_cy - THUMB_SIZE // 2

    thumb_url = getattr(track, "artwork", None) or getattr(track, "thumbnail", None)
    thumb_img = await _fetch_thumbnail(thumb_url) if thumb_url else None

    # Glowing ring behind thumbnail
    ring_size = THUMB_SIZE + 8
    ring_layer = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    ring_draw = ImageDraw.Draw(ring_layer)
    ring_cx = thumb_x + THUMB_SIZE // 2
    ring_cy_pos = thumb_y + THUMB_SIZE // 2

    # Outer glow
    for gr in range(20, 0, -1):
        alpha = int(20 * (gr / 20))
        offset = (THUMB_SIZE // 2) + gr + 4
        ring_draw.ellipse(
            [(ring_cx - offset, ring_cy_pos - offset),
             (ring_cx + offset, ring_cy_pos + offset)],
            fill=(ACCENT_PURPLE[0], ACCENT_PURPLE[1], ACCENT_PURPLE[2], alpha),
        )
    card = Image.alpha_composite(card, ring_layer)
    draw = ImageDraw.Draw(card)

    # Ring border
    ring_offset = THUMB_SIZE // 2 + 4
    draw.ellipse(
        [(ring_cx - ring_offset, ring_cy_pos - ring_offset),
         (ring_cx + ring_offset, ring_cy_pos + ring_offset)],
        outline=ACCENT_PURPLE + (120,),
        width=2,
    )

    if thumb_img:
        thumb_img = thumb_img.resize((THUMB_SIZE, THUMB_SIZE), Image.LANCZOS)
        # Apply circular mask
        circ_mask = _circle_mask(THUMB_SIZE)
        card.paste(thumb_img, (thumb_x, thumb_y), circ_mask)
    else:
        # Circular placeholder
        draw.ellipse(
            [(thumb_x, thumb_y),
             (thumb_x + THUMB_SIZE, thumb_y + THUMB_SIZE)],
            fill=(40, 30, 60, 200),
        )
        note_font = _load_font(50, bold=True)
        draw.text(
            (thumb_x + THUMB_SIZE // 2, thumb_y + THUMB_SIZE // 2),
            "♫",
            fill=TEXT_DIM,
            font=note_font,
            anchor="mm",
        )

    # ── Text area ───────────────────────────────────────────────
    text_x = thumb_x + THUMB_SIZE + PADDING + 12
    text_max_w = CARD_W - text_x - PADDING - 12

    # Fonts — large enough to be readable when Discord scales the image
    font_title   = _load_font(36, bold=True)
    font_artist  = _load_font(24)
    font_meta    = _load_font(20)
    font_badge   = _load_font(14, bold=True)
    font_time    = _load_font(16, bold=True)

    # Source badge (pill shape)
    source_label = _get_source_label(track)
    badge_y = thumb_y + 2
    _draw_source_badge(draw, text_x, badge_y, source_label.upper(), font_badge)

    # Song title (with shadow)
    title_y = badge_y + 34
    title_text = _truncate_text(draw, track.title or "Unknown", font_title, text_max_w)
    _draw_text_shadow(draw, (text_x, title_y), title_text, font_title, TEXT_WHITE, shadow_offset=2)

    # Artist (with subtle glow)
    artist_y = title_y + 48
    artist_text = _truncate_text(draw, track.author or "Unknown Artist", font_artist, text_max_w)
    # Glow layer for artist
    glow_artist = Image.new("RGBA", card.size, (0, 0, 0, 0))
    glow_a_draw = ImageDraw.Draw(glow_artist)
    glow_a_draw.text((text_x, artist_y), artist_text, fill=ACCENT_PURPLE + (50,), font=font_artist)
    glow_artist = glow_artist.filter(ImageFilter.GaussianBlur(radius=4))
    card = Image.alpha_composite(card, glow_artist)
    draw = ImageDraw.Draw(card)
    draw.text((text_x, artist_y), artist_text, fill=TEXT_GRAY, font=font_artist)

    # Requested by (accent color)
    if requester:
        req_y = artist_y + 34
        req_text = f"Requested by {requester.display_name}"
        req_text = _truncate_text(draw, req_text, font_meta, text_max_w)
        draw.text((text_x, req_y), req_text, fill=ACCENT_CYAN, font=font_meta)

    # ── Wavy progress bar ───────────────────────────────────────
    bar_y = CARD_H - PADDING - BAR_H - 24
    bar_width = text_max_w

    duration = track.length if track.length else 0
    _draw_wavy_progress_bar(draw, card, text_x, bar_y, bar_width, position, duration)

    # Refresh draw after compositing in progress bar
    draw = ImageDraw.Draw(card)

    # Time labels
    time_y = bar_y + BAR_H + WAVE_AMP + 8
    pos_text = format_duration(position)
    dur_text = format_duration(duration) if duration > 0 else "LIVE"
    draw.text((text_x, time_y), pos_text, fill=TEXT_DIM, font=font_time)
    dur_bbox = draw.textbbox((0, 0), dur_text, font=font_time)
    dur_w = dur_bbox[2] - dur_bbox[0]
    draw.text((text_x + bar_width - dur_w, time_y), dur_text, fill=TEXT_DIM, font=font_time)

    # ── Apply outer rounded mask ────────────────────────────────
    final = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    outer_mask = _round_corner_mask((CARD_W, CARD_H), CORNER_RADIUS)
    final.paste(card, (0, 0), outer_mask)

    # ── Export ──────────────────────────────────────────────────
    buf = io.BytesIO()
    final.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return discord.File(buf, filename="music_card.png")
