"""Core layout: collect images, fit them into slots, compose pages, write PDF."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

from .config import Config

# High-quality resampling filter for resize operations.
_RESAMPLE = Image.Resampling.LANCZOS


def collect_images(folder: str | Path, extensions: tuple[str, ...]) -> list[Path]:
    """Return image paths in *folder* matching *extensions*, sorted by name.

    Sorting is case-insensitive by filename so the layout order is predictable.
    """
    exts = {e.lower().lstrip(".") for e in extensions}
    folder = Path(folder)
    paths = [
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower().lstrip(".") in exts
    ]
    return sorted(paths, key=lambda p: p.name.lower())


def fit_image(img: Image.Image, size: tuple[int, int], mode: str, background: str) -> Image.Image:
    """Resize *img* to *size* (w, h) pixels using the given fit *mode*.

    - ``stretch``: resize to exactly *size*, ignoring aspect ratio.
    - ``fill``: scale to cover *size* preserving aspect, then center-crop.
    - ``fit``: scale to fit inside *size* preserving aspect, centered on a
      *background*-colored tile (letterbox).
    """
    target_w, target_h = size
    if target_w <= 0 or target_h <= 0:
        raise ValueError(f"invalid target size: {size}")

    if mode == "stretch":
        return img.resize((target_w, target_h), _RESAMPLE)

    src_w, src_h = img.size
    if mode == "fill":
        scale = max(target_w / src_w, target_h / src_h)
        scaled = img.resize(
            (max(1, round(src_w * scale)), max(1, round(src_h * scale))), _RESAMPLE
        )
        left = (scaled.width - target_w) // 2
        top = (scaled.height - target_h) // 2
        return scaled.crop((left, top, left + target_w, top + target_h))

    if mode == "fit":
        scale = min(target_w / src_w, target_h / src_h)
        scaled = img.resize(
            (max(1, round(src_w * scale)), max(1, round(src_h * scale))), _RESAMPLE
        )
        tile = Image.new("RGB", (target_w, target_h), background)
        offset = ((target_w - scaled.width) // 2, (target_h - scaled.height) // 2)
        tile.paste(scaled, offset)
        return tile

    raise ValueError(f"unknown fit mode: {mode!r}")  # pragma: no cover


def _prepare_image(path: Path, cfg: Config, target_px: tuple[int, int]) -> Image.Image:
    """Open, flatten, rotate, and fit a single source image to *target_px*."""
    with Image.open(path) as raw:
        img = raw.convert("RGBA") if raw.mode in ("RGBA", "LA", "P") else raw.convert("RGB")

        # Flatten transparency onto the background so PDF output is opaque RGB.
        if img.mode == "RGBA":
            flat = Image.new("RGB", img.size, cfg.background)
            flat.paste(img, mask=img.split()[-1])
            img = flat
        else:
            img = img.convert("RGB")

        if cfg.rotate:
            img = img.rotate(-cfg.rotate, expand=True)  # PIL rotates counter-clockwise

        return fit_image(img, target_px, cfg.fit, cfg.background)


def compose_pages(cfg: Config, images: list[Path], verbose: bool = False) -> list[Image.Image]:
    """Render all *images* into a list of full-page RGB canvases."""
    page_w = cfg.to_px(cfg.page_width)
    page_h = cfg.to_px(cfg.page_height)
    card_w = cfg.to_px(cfg.card_width)
    card_h = cfg.to_px(cfg.card_height)
    margin_l = cfg.to_px(cfg.margin_left)
    margin_t = cfg.to_px(cfg.margin_top)
    gap_x = cfg.to_px(cfg.gap_x)
    gap_y = cfg.to_px(cfg.gap_y)
    bleed_x = cfg.to_px(cfg.bleed_x)
    bleed_y = cfg.to_px(cfg.bleed_y)

    per_page = cfg.columns * cfg.rows

    # A starting offset leaves that many leading slots blank before the first
    # image; model it as leading empty slots in the placement sequence.
    slots: list[Path | None] = [None] * cfg.offset + list(images)
    page_count = max(1, math.ceil(len(slots) / per_page))

    # Each image is rendered to the slot grown by bleed on every side, then
    # pasted offset outward so the artwork overflows the cut line.
    target_px = (card_w + 2 * bleed_x, card_h + 2 * bleed_y)

    if verbose:
        print(f"  page size:   {page_w} x {page_h} px ({cfg.dpi} DPI)")
        print(f"  card slot:   {card_w} x {card_h} px  (+bleed -> {target_px[0]} x {target_px[1]})")
        print(f"  grid:        {cfg.columns} cols x {cfg.rows} rows = {per_page} per page")
        offset_note = f", offset {cfg.offset}" if cfg.offset else ""
        print(f"  images:      {len(images)}{offset_note} -> {page_count} page(s)")

    pages: list[Image.Image] = []
    for page_index in range(page_count):
        canvas = Image.new("RGB", (page_w, page_h), cfg.background)
        start = page_index * per_page
        chunk = slots[start : start + per_page]

        for slot, path in enumerate(chunk):
            if path is None:  # leading offset slot, left blank
                continue
            col = slot % cfg.columns
            row = slot // cfg.columns
            slot_x = margin_l + col * (card_w + gap_x)
            slot_y = margin_t + row * (card_h + gap_y)
            prepared = _prepare_image(path, cfg, target_px)
            canvas.paste(prepared, (slot_x - bleed_x, slot_y - bleed_y))

        pages.append(canvas)

    return pages


def _draw_test_card(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    bleed_x: int,
    bleed_y: int,
    line_w: int,
    color: str = "black",
) -> None:
    """Draw one test-sheet card: bleed + cut outlines and an up-arrow.

    ``(x, y)`` is the slot's top-left (the non-bleed/cut corner); ``w`` x ``h`` is
    the card slot size in pixels; bleed extends the outer rectangle outward.
    """
    # Outer rectangle at the full bleed size (only when there is bleed to show).
    if bleed_x > 0 or bleed_y > 0:
        draw.rectangle(
            [x - bleed_x, y - bleed_y, x + w + bleed_x, y + h + bleed_y],
            outline=color,
            width=line_w,
        )
    # Inner rectangle at the non-bleed (cut) size.
    draw.rectangle([x, y, x + w, y + h], outline=color, width=line_w)

    # Up-arrow centered in the card to denote orientation.
    cx = x + w // 2
    tip_y = y + int(h * 0.30)
    tail_y = y + int(h * 0.70)
    head_h = int(h * 0.10)
    head_w = int(w * 0.12)
    draw.line([(cx, tail_y), (cx, tip_y)], fill=color, width=line_w)  # shaft
    draw.line([(cx - head_w, tip_y + head_h), (cx, tip_y)], fill=color, width=line_w)
    draw.line([(cx + head_w, tip_y + head_h), (cx, tip_y)], fill=color, width=line_w)


def compose_test_page(cfg: Config, verbose: bool = False) -> Image.Image:
    """Render a single-page test sheet for the configured template.

    Every grid slot is drawn (no images needed) with a bleed-size outline, a
    cut-size outline, and an up-arrow, so a printed copy can be checked against
    a physical template.
    """
    page_w = cfg.to_px(cfg.page_width)
    page_h = cfg.to_px(cfg.page_height)
    card_w = cfg.to_px(cfg.card_width)
    card_h = cfg.to_px(cfg.card_height)
    margin_l = cfg.to_px(cfg.margin_left)
    margin_t = cfg.to_px(cfg.margin_top)
    gap_x = cfg.to_px(cfg.gap_x)
    gap_y = cfg.to_px(cfg.gap_y)
    bleed_x = cfg.to_px(cfg.bleed_x)
    bleed_y = cfg.to_px(cfg.bleed_y)

    # A thin, crisp line so alignment can be judged precisely (~2 px at 300 DPI).
    line_w = max(1, round(cfg.dpi / 150))

    if verbose:
        print(f"  mode:        test sheet (1 page)")
        print(f"  page size:   {page_w} x {page_h} px ({cfg.dpi} DPI)")
        print(f"  card slot:   {card_w} x {card_h} px  (bleed {bleed_x} x {bleed_y} px)")
        print(f"  grid:        {cfg.columns} cols x {cfg.rows} rows")

    canvas = Image.new("RGB", (page_w, page_h), cfg.background)
    draw = ImageDraw.Draw(canvas)
    for row in range(cfg.rows):
        for col in range(cfg.columns):
            slot_x = margin_l + col * (card_w + gap_x)
            slot_y = margin_t + row * (card_h + gap_y)
            _draw_test_card(draw, slot_x, slot_y, card_w, card_h, bleed_x, bleed_y, line_w)

    return canvas


def build_test_sheet(cfg: Config, verbose: bool = False) -> int:
    """Render and save a single-page template test sheet. Returns page count (1)."""
    page = compose_test_page(cfg, verbose=verbose)
    output = Path(cfg.output).expanduser()
    page.save(output, "PDF", resolution=float(cfg.dpi))
    if verbose:
        print(f"  wrote:       {output} (1 page)")
    return 1


def build_pdf(cfg: Config, verbose: bool = False) -> int:
    """Build the output PDF from the configured input folder.

    Returns the number of pages written. Raises on missing/empty input.
    """
    images = collect_images(cfg.input, cfg.extensions)
    if not images:
        raise FileNotFoundError(
            f"no images matching {cfg.extensions} found in {cfg.input}"
        )

    pages = compose_pages(cfg, images, verbose=verbose)

    output = Path(cfg.output).expanduser()
    pages[0].save(
        output,
        "PDF",
        save_all=True,
        append_images=pages[1:],
        resolution=float(cfg.dpi),
    )
    if verbose:
        print(f"  wrote:       {output} ({len(pages)} page(s))")
    return len(pages)
