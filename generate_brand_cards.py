#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate 600x600 brand logo cards from an Excel list of brands & logo URLs.
- Reads an Excel file with columns: "Prekės ženklas", "Oficiali svetainė", "Brandfetch (logo)", "Clearbit (logo)".
- Attempts to download the logo (Brandfetch first, then Clearbit, then official site's favicon).
- Computes a background color from the logo's dominant non-white color.
- Creates a 600x600 PNG with rounded corners and centered logo.
- Ensures contrast (recolors dark logos to white on dark backgrounds if needed).
- Saves results into ./output and bundles them into brand_logo_cards.zip

USAGE:
    python3 generate_brand_cards.py --excel brand_logo_links.xlsx --outdir output

DEPENDENCIES: see requirements.txt
"""

import argparse
import io
import math
import os
import re
import sys
import zipfile
from urllib.parse import urlparse

import pandas as pd
import requests
from PIL import Image, ImageOps, ImageDraw, ImageStat

# ---------------------------
# Utils
# ---------------------------

def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s]+", "_", value)
    return value or "brand"

def fetch_bytes(url: str, timeout=15) -> bytes:
    headers = {"User-Agent": "Mozilla/5.0 (LogoFetcher/1.0)"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.ok and r.content:
            return r.content
    except requests.RequestException:
        return b""
    return b""

def ensure_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return "https://" + url.lstrip("/")

def favicon_from_official_site(site_url: str) -> str:
    # Try /favicon.ico as a last resort
    if not site_url:
        return ""
    try:
        parsed = urlparse(site_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        return base + "/favicon.ico"
    except Exception:
        return ""

def open_image_auto(data: bytes) -> Image.Image:
    # Try to open as image, fallback to ICO
    try:
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        # Try ICO decoding
        try:
            im = Image.open(io.BytesIO(data))
            if im.format == "ICO":
                sizes = im.ico.getentryindex(0) if hasattr(im, "ico") else None
            return im.convert("RGBA")
        except Exception:
            raise

def dominant_color(img: Image.Image) -> tuple:
    # Reduce size for speed; ignore near-white pixels
    small = img.copy()
    small.thumbnail((64, 64), Image.LANCZOS)
    pixels = small.getdata()
    histogram = {}
    for r, g, b, a in pixels:
        if a < 10:
            continue
        # Ignore very bright/near white pixels
        if r > 240 and g > 240 and b > 240:
            continue
        key = (r, g, b)
        histogram[key] = histogram.get(key, 0) + 1
    if not histogram:
        return (245, 245, 245)
    return max(histogram.items(), key=lambda kv: kv[1])[0]

def relative_luminance(rgb):
    def channel(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

def contrast_ratio(rgb1, rgb2):
    L1 = relative_luminance(rgb1)
    L2 = relative_luminance(rgb2)
    L1, L2 = max(L1, L2), min(L1, L2)
    return (L1 + 0.05) / (L2 + 0.05)

def recolor_to_white(logo: Image.Image) -> Image.Image:
    # Convert non-transparent pixels to white, preserve alpha
    rgba = logo.convert("RGBA")
    data = rgba.getdata()
    new_data = []
    for r,g,b,a in data:
        if a == 0:
            new_data.append((r,g,b,a))
        else:
            new_data.append((255,255,255,a))
    rgba.putdata(new_data)
    return rgba

def fit_logo(logo: Image.Image, canvas_size=600, max_ratio=0.6):
    # Fit logo within canvas with margins (e.g., occupy up to 60% of width/height)
    target = int(canvas_size * max_ratio)
    w, h = logo.size
    scale = min(target / w, target / h)
    new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
    return logo.resize((new_w, new_h), Image.LANCZOS)

def rounded_mask(size, radius):
    w, h = size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0,0,w,h], radius=radius, fill=255)
    return mask

# ---------------------------
# Card generation
# ---------------------------

def make_card(logo_img: Image.Image, out_path: str, bg_rgb=(245,245,245), canvas=600, radius=40):
    # Compute bg from logo dominant color if not provided
    if bg_rgb is None:
        bg_rgb = dominant_color(logo_img)

    # Create background
    card = Image.new("RGBA", (canvas, canvas), (0,0,0,0))
    bg = Image.new("RGBA", (canvas, canvas), bg_rgb+(255,))
    mask = rounded_mask((canvas, canvas), radius)
    card.paste(bg, (0,0), mask)

    # Prepare logo
    logo = logo_img.copy()
    logo = fit_logo(logo, canvas_size=canvas, max_ratio=0.62)

    # Ensure contrast: if both bg and logo are dark, recolor logo to white
    # Estimate logo average color
    stat = ImageStat.Stat(logo.split()[0:3])
    avg_rgb = tuple(int(c) for c in stat.mean)
    cr = contrast_ratio(avg_rgb, bg_rgb)
    if cr < 2.5:
        logo = recolor_to_white(logo)
        # Recompute contrast for sanity (logo now white)
        # not strictly needed

    # Center
    lw, lh = logo.size
    x = (canvas - lw)//2
    y = (canvas - lh)//2
    card.paste(logo, (x, y), logo)

    # Save PNG
    card = card.convert("RGBA")
    card.save(out_path, format="PNG")

# ---------------------------
# Main flow
# ---------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel", required=True, help="Path to Excel file (brand list)")
    ap.add_argument("--outdir", default="output", help="Output directory for PNGs")
    ap.add_argument("--zipname", default="brand_logo_cards.zip", help="Zip archive name")
    ap.add_argument("--radius", type=int, default=40, help="Corner radius (px)")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    df = pd.read_excel(args.excel)

    # Expected columns
    name_col = "Prekės ženklas"
    bf_col = "Brandfetch (logo)"
    cb_col = "Clearbit (logo)"
    site_col = "Oficiali svetainė"

    missing = [c for c in [name_col, bf_col, cb_col, site_col] if c not in df.columns]
    if missing:
        print("Trūksta stulpelių Excel faile:", missing)
        sys.exit(1)

    results = []
    for idx, row in df.iterrows():
        brand = str(row[name_col]).strip()
        if not brand or brand.lower() == "nan":
            continue

        brand_slug = slugify(brand)
        out_path = os.path.join(args.outdir, f"{brand_slug}.png")

        # URL priority: Brandfetch -> Clearbit -> favicon from official site
        urls = []
        bf_url = str(row.get(bf_col, "") or "").strip()
        cb_url = str(row.get(cb_col, "") or "").strip()
        site_url = str(row.get(site_col, "") or "").strip()

        if bf_url:
            urls.append(bf_url)
        if cb_url:
            urls.append(cb_url)
        if site_url:
            fav = None
            # try site_url/favicon.ico as last resort
            if site_url.startswith("http"):
                fav = site_url.rstrip("/") + "/favicon.ico"
            else:
                fav = "https://" + site_url.strip("/").rstrip("/") + "/favicon.ico"
            urls.append(fav)

        logo_img = None
        used_url = None
        for u in urls:
            try:
                data = fetch_bytes(u)
                if not data:
                    continue
                img = open_image_auto(data)
                logo_img = img
                used_url = u
                break
            except Exception:
                continue

        if logo_img is None:
            print(f"[SKIP] Nepavyko atsisiųsti logotipo: {brand}")
            continue

        # Build card
        try:
            bg = dominant_color(logo_img)
            make_card(logo_img, out_path, bg_rgb=bg, canvas=600, radius=args.radius)
            results.append((brand, out_path, used_url))
            print(f"[OK] {brand} -> {out_path}")
        except Exception as e:
            print(f"[ERR] {brand}: {e}")

    # Zip results
    zip_path = os.path.join(os.getcwd(), args.zipname)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for _, out_path, _ in results:
            zf.write(out_path, arcname=os.path.basename(out_path))

    print(f"\nSukurta {len(results)} kortelių. ZIP: {zip_path}")

if __name__ == "__main__":
    main()
