
# Brand Logo Cards Generator

This toolkit converts an Excel list of brands and logo URLs into **600×600 PNG cards** with:
- individual brand-derived background color
- rounded corners (default 40px)
- centered official logo
- consistent, flat style

> You indicated you have permission to use these logos for identification/informational purposes. Please verify you comply with any trademark and brand guidelines. Add "not affiliated" disclaimers if required.

## Files
- `generate_brand_cards.py` – main script
- `requirements.txt` – Python dependencies
- Your Excel input: `brand_logo_links.xlsx` (you provided this already)

## Excel format
Required columns (exact names):
- `Prekės ženklas`
- `Oficiali svetainė`
- `Brandfetch (logo)`
- `Clearbit (logo)`

## How it works
1. Attempts download in priority order: **Brandfetch → Clearbit → official-site `/favicon.ico`** fallback.
2. Computes a **dominant non-white color** from the logo to use as background.
3. Fits logo into canvas, and if contrast is low, recolors the logo to **white** to maintain clarity.
4. Exports each card as **PNG** into `./output` and bundles them into `brand_logo_cards.zip`.

## Usage
```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python generate_brand_cards.py --excel brand_logo_links.xlsx --outdir output --zipname brand_logo_cards.zip
```

## Notes
- If any brand fails to download (URL unavailable), it's skipped with a console message.
- You can safely re-run; it will overwrite existing PNGs.
- If you want to enforce *white-only* logos (monochrome), you can set the `recolor_to_white` call unconditionally.
- If some brands require **official brand color** rather than computed dominant color, we can add a small YAML mapping to override backgrounds per brand.

## Legal
- Ensure usage aligns with your permissions and applicable law (EU InfoSoc, local copyright and trademark rules).
- When displaying on your site, add a short footer note such as: _"All trademarks and brands are the property of their respective owners. Not affiliated."_

