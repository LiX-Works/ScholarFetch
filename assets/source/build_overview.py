"""ScholarFetch overview, journal style (a/b/c panels), refined from the main session's A_journal_v2.

Usage: py build_overview.py [dark|light] -> writes overview.svg/.html next to this file.
The default variant is dark: the dedicated browser is the one dark focal block. The light variant uses an all-light,
compact layout.
"""
import sys
from pathlib import Path

VARIANT = sys.argv[1] if len(sys.argv) > 1 else "dark"
if VARIANT not in {"dark", "light"}:
    raise SystemExit("variant must be 'dark' or 'light'")
DARK = VARIANT == "dark"
W, H = 1600, 590
INK, SUB, LINE = "#1F2933", "#475467", "#3F4A56"
TEAL, TEAL0, TEAL1 = "#1F6F8B", "#174E66", "#24718D"
AMBER, AMBER_T, AMBER_BG = "#C07A2C", "#8A5317", "#FDF3E7"
OK = "#2E7D5B"

out = []
add = out.append


def text(x, y, s, size=22, weight=400, fill=INK, anchor="start"):
    s = s.replace("&", "&amp;")
    add(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{s}</text>')


def arrow(x1, y1, x2, y2, color=LINE, w=2.4):
    # shaft stops inside the head so the tip stays sharp
    import math
    n = math.hypot(x2 - x1, y2 - y1); ux, uy = (x2 - x1) / n, (y2 - y1) / n
    L, h = 14, 7
    add(f'<path d="M{x1} {y1} L{x2 - .6 * L * ux:.1f} {y2 - .6 * L * uy:.1f}" stroke="{color}" stroke-width="{w}" fill="none"/>')
    bx, by = x2 - L * ux, y2 - L * uy
    add(f'<path d="M{x2} {y2} L{bx - h * uy:.1f} {by + h * ux:.1f} L{bx + h * uy:.1f} {by - h * ux:.1f}Z" fill="{color}"/>')


def panel(x, letter, title, color=INK):
    text(x, 62, letter, 44, 700, "#111")
    text(x + 44, 60, title, 32, 600, color)


# ---------- a: find and check ----------
panel(40, "a", "Find and check")
for i, s in enumerate(("Topic", "References", "DOI / link")):
    bx = 50 + i * 160
    add(f'<rect x="{bx}" y="94" width="150" height="56" rx="6" fill="#fff" stroke="{LINE}" stroke-width="2"/>')
    text(bx + 75, 130, s, 22, 400, "#333", "middle")
add(f'<path d="M125 150V170M285 150V170M445 150V170M125 170H445" stroke="{LINE}" stroke-width="2" fill="none"/>')
arrow(285, 170, 285, 196)
add(f'<rect x="50" y="198" width="470" height="256" rx="10" fill="#F7F7F7" stroke="{LINE}" stroke-width="2"/>')
text(74, 242, "Search 6 databases", 28, 600)
for i, (l, r) in enumerate((("Crossref", "OpenAlex"), ("PubMed", "Europe PMC"), ("Semantic Scholar", "arXiv"))):
    text(74, 284 + i * 36, l, 22, 400, "#444")
    text(310, 284 + i * 36, r, 22, 400, "#444")
# metadata check folded into the search box as a slim strip
add(f'<path d="M50 394H520" stroke="#D0D5DD" stroke-width="1.6"/>')
add(f'<circle cx="86" cy="424" r="14" fill="{OK}"/>')
add(f'<path d="M79 424l5 5 9-10" stroke="#fff" stroke-width="3" fill="none"/>')
text(112, 432, "Title, authors, year, DOI checked", 22, 400, "#444")
arrow(520, 326, 628, 326)

# ---------- b: download from the publisher ----------
panel(590, "b", "Download from the publisher", TEAL)
# publisher pages tucked behind the browser's left edge (different layouts per publisher)
for i, (dx, dy, head) in enumerate(((48, -40, "#D5E3D5"), (24, -20, "#E3D5C5"), (0, 0, "#C9D6DF"))):
    x, y = 646 + dx, 236 + dy
    add(f'<rect x="{x}" y="{y}" width="150" height="190" rx="5" fill="#fff" stroke="#9A9A9A" stroke-width="1.6"/>')
    add(f'<rect x="{x}" y="{y}" width="150" height="26" rx="5" fill="{head}"/>')
    if i == 2:
        for k, w in enumerate((96, 110, 78, 104)):
            add(f'<rect x="{x + 14}" y="{y + 42 + k * 17}" width="{w}" height="7" rx="3.5" fill="#D6D6D6"/>')
bx0, by0, bw, bh = 820, 168, 420, 284
if DARK:
    add(f'<rect x="{bx0}" y="{by0}" width="{bw}" height="{bh}" rx="12" fill="url(#browser)"/>')
    add(f'<rect x="{bx0}" y="{by0}" width="{bw}" height="44" rx="12" fill="#123E52"/>')
    add(f'<rect x="{bx0}" y="{by0 + 30}" width="{bw}" height="14" fill="#123E52"/>')
    dots, pill_fill, pill_stroke, head_col, step_fill, num_col, body = "#7FA9BC", "#1B5874", "#2D6E8A", "#FFFFFF", "#FFFFFF", TEAL0, "#E8F1F5"
else:
    add(f'<rect x="{bx0}" y="{by0}" width="{bw}" height="{bh}" rx="12" fill="#FFFFFF"/>')
    add(f'<rect x="{bx0}" y="{by0}" width="{bw}" height="44" rx="12" fill="#EAF2F5"/>')
    add(f'<rect x="{bx0}" y="{by0 + 30}" width="{bw}" height="14" fill="#EAF2F5"/>')
    add(f'<rect x="{bx0}" y="{by0}" width="{bw}" height="{bh}" rx="12" fill="none" stroke="{TEAL}" stroke-width="2.6"/>')
    dots, pill_fill, pill_stroke, head_col, step_fill, num_col, body = "#9DB6C2", "#FFFFFF", "#C5D6DE", TEAL, TEAL, "#FFFFFF", "#333333"
for k in range(3):
    add(f'<circle cx="{bx0 + 22 + k * 19}" cy="{by0 + 22}" r="5.5" fill="{dots}"/>')
add(f'<rect x="{bx0 + 82}" y="{by0 + 11}" width="{bw - 100}" height="22" rx="11" fill="{pill_fill}" stroke="{pill_stroke}"/>')
text(bx0 + 26, by0 + 94, "Dedicated browser", 30, 700, head_col)
for k, s in enumerate(("Reaches the article page", "Finds the PDF link", "Saves the PDF")):
    cy = by0 + 142 + k * 46
    add(f'<circle cx="{bx0 + 40}" cy="{cy}" r="15" fill="{step_fill}"/>')
    text(bx0 + 40, cy + 7, str(k + 1), 19, 700, num_col, "middle")
    text(bx0 + 68, cy + 8, s, 24, 400, body)
# your access, docked on the browser's top edge
ax0, aw, ay = bx0 + 24, 372, by0 - 46
add(f'<rect x="{ax0}" y="{ay}" width="{aw}" height="52" rx="26" fill="{AMBER_BG}" stroke="{AMBER}" stroke-width="2.2"/>')
add(f'<circle cx="{ax0 + 32}" cy="{ay + 26}" r="9" fill="none" stroke="{AMBER}" stroke-width="3.2"/>')
add(f'<path d="M{ax0 + 41} {ay + 26}H{ax0 + 64}M{ax0 + 56} {ay + 26}V{ay + 36}M{ax0 + 62} {ay + 26}V{ay + 34}" stroke="{AMBER}" stroke-width="3.2" fill="none"/>')
text(ax0 + 76, ay + 34, "Your institutional access", 24, 600, AMBER_T)
# the saved PDF leaves through the bottom edge
px, py = 930, by0 + bh + 18
arrow(px + 30, by0 + bh + 2, px + 30, py + 2, TEAL)
add(f'<path d="M{px} {py + 4}H{px + 52}L{px + 72} {py + 24}V{py + 96}H{px}Z" fill="#fff" stroke="{LINE}" stroke-width="2"/>')
add(f'<path d="M{px + 52} {py + 4}V{py + 24}H{px + 72}" fill="none" stroke="{LINE}" stroke-width="2"/>')
add(f'<rect x="{px - 10}" y="{py + 42}" width="58" height="28" rx="3" fill="{TEAL}"/>')
text(px + 19, py + 63, "PDF", 19, 700, "#fff", "middle")
add(f'<circle cx="{px + 72}" cy="{py + 92}" r="17" fill="{OK}"/>')
add(f'<path d="M{px + 63} {py + 92}l7 7 12-14" stroke="#fff" stroke-width="3.2" fill="none"/>')
text(px + 100, py + 66, "Identity checked", 24, 600, INK)

# ---------- c: outputs ----------
add('<path d="M570 96V560M1272 96V560" stroke="#E6E6E6" stroke-width="1.5"/>')
panel(1300, "c", "Outputs")
add(f'<path d="M1302 110H1326L1338 122V154H1302Z" fill="#fff" stroke="{LINE}" stroke-width="2"/>')
text(1356, 142, "Verified PDFs", 26, 600)
add(f'<path d="M1302 196H1336M1302 208H1336M1302 220H1326M1302 232H1332" stroke="{LINE}" stroke-width="2.6"/>')
text(1356, 222, "Records", 26, 600)
text(1356, 254, "RIS / BibTeX", 22, 400, "#555")
add(f'<path d="M1305 292V338M1305 294H1334L1326 305L1334 316H1305" fill="none" stroke="#888" stroke-width="2.4"/>')
text(1356, 320, "Follow-up list", 26, 600)
# the human decision: solid mark, as in the other figures
add(f'<rect x="1300" y="380" width="270" height="110" rx="12" fill="{AMBER_BG}" stroke="{AMBER}" stroke-width="2"/>')
add(f'<circle cx="1334" cy="418" r="11" fill="{AMBER}"/>')
add(f'<rect x="1317" y="432" width="34" height="22" rx="10" fill="{AMBER}"/>')
text(1370, 428, "You decide", 26, 700, AMBER_T)
text(1370, 462, "what to cite", 26, 400, AMBER_T)

defs = f'''<defs><linearGradient id="browser" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="{TEAL0}"/><stop offset="1" stop-color="{TEAL1}"/></linearGradient></defs>'''
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
       f'font-family="Helvetica Neue,Helvetica,Arial,sans-serif" role="img" aria-labelledby="t d">\n'
       '<title id="t">ScholarFetch overview</title>\n'
       '<desc id="d">(a) Candidates from six databases, with metadata checked. (b) Each PDF is downloaded from the '
       'publisher in a dedicated browser using your own institutional access, then identity-checked. (c) Outputs: '
       'verified PDFs, RIS or BibTeX records, a follow-up list; you decide what to cite.</desc>\n'
       f'{defs}<rect width="{W}" height="{H}" fill="#fff"/>\n' + "\n".join(out) + "\n</svg>\n")
here = Path(__file__).resolve().parent
(here / "overview.svg").write_text(svg, encoding="utf-8")
(here / "overview.html").write_text(
    '<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:#fff}svg{display:block}</style>' + svg,
    encoding="utf-8")
print(VARIANT)
