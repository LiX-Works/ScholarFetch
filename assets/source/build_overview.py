"""Build the README overview figure (assets/overview.png) with the Python standard library.

Writes overview.svg and an overview.html wrapper next to the --output path; render the
HTML to PNG at 2x (3200 x 1440), e.g. with headless Chrome or Edge.
"""
from pathlib import Path
import argparse
import math
from xml.sax.saxutils import escape

cli = argparse.ArgumentParser(description=__doc__)
cli.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "overview.svg")
args = cli.parse_args()

W, H = 1600, 720
FONT = "Arial,Helvetica,sans-serif"
C = dict(
    ink="#16203A", sub="#2C3850", line="#2E3A55", card="#FFFFFF", cardStroke="#C3CDDD",
    amber="#E8960F", amberText="#A9650A", amberTint="#FFF3DC", lead0="#22386A", lead1="#3866A6",
    search="#36579A", searchTint="#E4ECF8", verify="#5A3CC2", verifyTint="#F1ECFD",
    ok="#2F8A5F", okTint="#E3F4EA", bad="#C2413B", badTint="#FBE5E3", cyan="#7FE3EE",
)

out = []
add = out.append


def f(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def text(x, y, s, size=26, weight=700, fill=C["ink"], anchor="start", extra=""):
    add(f'<text x="{f(x)}" y="{f(y)}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
        f'text-anchor="{anchor}" {extra}>{escape(s)}</text>')


def line(d, stroke, width, extra=""):
    add(f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{width}" '
        f'stroke-linecap="round" stroke-linejoin="round" {extra}/>')


def arrow(x1, y1, x2, y2, color=C["line"], width=5.5, size=22, half=11):
    # The shaft stops inside the head, so the tip stays a sharp point.
    n = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / n, (y2 - y1) / n
    add(f'<path d="M{f(x1)} {f(y1)} L{f(x2 - .6 * size * ux)} {f(y2 - .6 * size * uy)}" '
        f'fill="none" stroke="{color}" stroke-width="{width}"/>')
    bx, by = x2 - size * ux, y2 - size * uy
    add(f'<path d="M{f(x2)} {f(y2)} L{f(bx - half * uy)} {f(by + half * ux)} '
        f'L{f(bx + half * uy)} {f(by - half * ux)}Z" fill="{color}"/>')


def card(x, y, w, h, rx=24, stroke=C["cardStroke"], fill=C["card"], sw=1.8):
    add(f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" rx="{rx}" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="{sw}" filter="url(#shadow)"/>')


def check(cx, cy, color, r=15, tint=None):
    add(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{r}" fill="{tint or color}"/>')
    line(f"M{f(cx - r * .45)} {f(cy)} l{f(r * .3)} {f(r * .32)} l{f(r * .55)} {f(-r * .62)}",
         color if tint else "#FFFFFF", 3.4)


def cross(cx, cy, r=15):
    add(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{r}" fill="{C["bad"]}"/>')
    k = r * .38
    line(f"M{f(cx - k)} {f(cy - k)} L{f(cx + k)} {f(cy + k)} M{f(cx + k)} {f(cy - k)} L{f(cx - k)} {f(cy + k)}", "#FFFFFF", 3.4)


def badge(x, y, n, color):
    add(f'<circle cx="{x}" cy="{y}" r="19" fill="{color}"/>')
    text(x, y + 9, str(n), 24, 700, "#FFFFFF", "middle")


# ---------- layout ----------
COLS = [dict(x=40, w=440), dict(x=560, w=400), dict(x=1040, w=520)]
for c in COLS:
    c["cx"] = c["x"] + c["w"] / 2
EY, EH = 28, 64          # entry chips
SY, SH = 160, 380        # stage cards
OY, OH = 620, 64         # output chips
g = 7


def entry(col, label):
    w = 330
    x = col["cx"] - w / 2
    card(x, EY, w, EH, 32)
    text(col["cx"], EY + 41, label, 24, 700, C["ink"], "middle")
    arrow(col["cx"], EY + EH + g, col["cx"], SY - g)


def output(cx, w, label, accent, tint, size=23):
    x = cx - w / 2
    card(x, OY, w, OH, 32, accent if tint else C["cardStroke"], tint or C["card"], 2.4 if tint else 1.8)
    add(f'<circle cx="{f(x + 34)}" cy="{OY + OH / 2}" r="9" fill="{accent}"/>')
    text(x + 54, OY + 40, label, size, 700, C["amberText"] if tint else C["ink"])


# ---------- entries ----------
entry(COLS[0], "Start from a topic")
entry(COLS[1], "Start from a reference list")
entry(COLS[2], "Start from a DOI or link")

# ---------- 1 search ----------
c = COLS[0]
card(c["x"], SY, c["w"], SH)
badge(c["x"] + 46, SY + 46, 1, C["search"])
text(c["x"] + 80, SY + 56, "Search broadly", 30)
px, py, pw, ph = c["x"] + 28, SY + 86, c["w"] - 56, 228
add(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="16" fill="{C["searchTint"]}"/>')
sources = ["Crossref", "PubMed", "OpenAlex", "Europe PMC", "Semantic Scholar", "arXiv"]  # arXiv: search only, dashed border
bw, bh, gx, gy = 172, 50, 16, 16
bx0 = px + (pw - (2 * bw + gx)) / 2
by0 = py + (ph - (3 * bh + 2 * gy)) / 2
for k, s in enumerate(sources):
    i, j = k % 2, k // 2
    x, y = bx0 + i * (bw + gx), by0 + j * (bh + gy)
    muted = s == "arXiv"
    add(f'<rect x="{f(x)}" y="{f(y)}" width="{bw}" height="{bh}" rx="12" fill="#FFFFFF" '
        f'stroke="#9DB2D6" stroke-width="1.6"{' stroke-dasharray="6 5"' if muted else ''}/>')
    text(x + bw / 2, y + 32, s, 18 if len(s) > 12 else 21, 700, C["search"], "middle")
text(c["cx"], SY + 352, "Six databases, deduplicated", 24, 400, C["sub"], "middle")

# ---------- 2 verify ----------
c = COLS[1]
card(c["x"], SY, c["w"], SH)
badge(c["x"] + 46, SY + 46, 2, C["verify"])
text(c["x"] + 80, SY + 56, "Verify metadata", 30)
px, py, pw = c["x"] + 28, SY + 86, c["w"] - 56
add(f'<rect x="{px}" y="{py}" width="{pw}" height="228" rx="16" fill="{C["verifyTint"]}"/>')
rows = [("Title", True), ("Authors", True), ("Year", False), ("DOI", True)]
rh = 46
ry0 = py + (228 - 4 * rh - 3 * 8) / 2
for k, (label, ok) in enumerate(rows):
    y = ry0 + k * (rh + 8)
    add(f'<rect x="{px + 18}" y="{f(y)}" width="{pw - 36}" height="{rh}" rx="12" fill="{"#FFFFFF" if ok else C["badTint"]}"/>')
    text(px + 40, y + 31, label, 22, 700, C["ink"])
    if ok:
        check(px + pw - 50, y + rh / 2, C["ok"])
    else:
        text(px + pw - 76, y + 31, "conflict", 20, 700, C["bad"], "end")
        cross(px + pw - 50, y + rh / 2)
text(c["cx"], SY + 352, "Every field compared", 24, 400, C["sub"], "middle")

# ---------- 3 download (hero) ----------
c = COLS[2]
x, w = c["x"], c["w"]
add(f'<rect x="{x}" y="{SY}" width="{w}" height="{SH}" rx="28" fill="url(#leadGrad)" filter="url(#leadShadow)"/>')
add(f'<rect x="{x}" y="{SY}" width="{w}" height="{SH}" rx="28" fill="url(#sheen)"/>')
badge(x + 46, SY + 46, 3, C["amber"])
text(x + 80, SY + 57, "Download automatically", 32, 700, "#FFFFFF")
# icon row: publisher page -> dedicated browser -> verified PDF
iy = SY + 140
xs = [x + 95, x + w / 2, x + w - 95]
# publisher page
p0 = xs[0]
add(f'<rect x="{f(p0 - 34)}" y="{iy - 44}" width="68" height="88" rx="8" fill="#FFFFFF"/>')
add(f'<rect x="{f(p0 - 34)}" y="{iy - 44}" width="68" height="20" rx="8" fill="#C9D7EE"/>')
add(f'<rect x="{f(p0 - 34)}" y="{iy - 32}" width="68" height="8" fill="#C9D7EE"/>')
for k in range(4):
    line(f"M{f(p0 - 22)} {iy - 8 + k * 13}h{44 if k % 2 == 0 else 30}", "#8EA3C7", 3)
# browser window
b0 = xs[1]
add(f'<rect x="{f(b0 - 52)}" y="{iy - 40}" width="104" height="80" rx="10" fill="#0F1D3D" stroke="{C["cyan"]}" stroke-width="3"/>')
add(f'<path d="M{f(b0 - 52)} {iy - 22} h104" stroke="{C["cyan"]}" stroke-width="3"/>')
for k in range(3):
    add(f'<circle cx="{f(b0 - 40 + k * 11)}" cy="{iy - 31}" r="3.4" fill="{C["cyan"]}"/>')
# mouse pointer inside the browser
add(f'<path d="M0 0 L0 24 L6.5 18.5 L11 28 L15.5 26 L11 16.5 L19 16.5 Z" fill="{C["cyan"]}" stroke="#0F1D3D" '
    f'stroke-width="1.6" stroke-linejoin="round" transform="translate({f(b0 - 8)} {iy - 9})"/>')
# verified pdf
d0 = xs[2]
add(f'<path d="M{f(d0 - 34)} {iy - 44} h48 l20 20 v68 h-68z" fill="#FFFFFF"/>')
add(f'<path d="M{f(d0 + 14)} {iy - 44} v20 h20" fill="#C9D7EE"/>')
add(f'<rect x="{f(d0 - 44)}" y="{iy - 14}" width="50" height="24" rx="5" fill="#D64541"/>')
text(d0 - 19, iy + 4, "PDF", 17, 700, "#FFFFFF", "middle")
check(d0 + 30, iy + 34, "#FFFFFF", 17, C["ok"])
# connectors between icons
for a, b in ((xs[0] + 46, xs[1] - 64), (xs[1] + 64, xs[2] - 52)):
    arrow(a, iy, b, iy, C["amber"], 4.5, 18, 9)
for xx, (l1, l2) in zip(xs, [("Publisher", "page"), ("Dedicated", "browser"), ("Verified", "PDF")]):
    text(xx, iy + 78, l1, 21, 700, "#E7EEFA", "middle")
    text(xx, iy + 102, l2, 21, 700, "#E7EEFA", "middle")
# feature list
for k, s in enumerate(["Official publisher sources only", "Opens protected publisher pages", "Every PDF identity-checked"]):
    yy = SY + 292 + k * 33
    check(x + 52, yy - 7, "#FFFFFF", 11, C["amber"])
    text(x + 74, yy, s, 22, 700, "#FFFFFF")

# ---------- flow ----------
mid = SY + SH / 2
arrow(COLS[0]["x"] + COLS[0]["w"] + g, mid, COLS[1]["x"] - g, mid)
arrow(COLS[1]["x"] + COLS[1]["w"] + g, mid, COLS[2]["x"] - g, mid)

# ---------- outputs ----------
arrow(COLS[0]["cx"], SY + SH + g, COLS[0]["cx"], OY - g)
output(COLS[0]["cx"], 320, "Candidates + sources", C["search"], None)
arrow(COLS[1]["cx"], SY + SH + g, COLS[1]["cx"], OY - g)
output(COLS[1]["cx"] - 106, 202, "Match report", C["verify"], None, 21)
output(COLS[1]["cx"] + 106, 202, "RIS / BibTeX", C["verify"], None, 21)
d = COLS[2]
arrow(d["cx"], SY + SH + g, d["cx"], OY - g)
output(d["cx"] - 132, 248, "Checked PDFs", C["ok"], None)
output(d["cx"] + 132, 248, "Needs attention", C["amber"], C["amberTint"])

defs = f"""<defs>
  <linearGradient id="leadGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{C['lead0']}"/><stop offset="1" stop-color="{C['lead1']}"/></linearGradient>
  <linearGradient id="sheen" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".16"/><stop offset=".45" stop-color="#fff" stop-opacity="0"/></linearGradient>
  <filter id="shadow" x="-20%" y="-30%" width="140%" height="170%"><feDropShadow dx="0" dy="5" stdDeviation="8" flood-color="#16203A" flood-opacity=".10"/></filter>
  <filter id="leadShadow" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="10" stdDeviation="16" flood-color="#22386A" flood-opacity=".32"/></filter>
</defs>"""
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
       f'font-family="{FONT}" role="img" aria-labelledby="title desc">\n'
       '<title id="title">ScholarFetch overview</title>\n'
       '<desc id="desc">Start from a topic, a reference list, or a DOI or link. ScholarFetch searches six scholarly databases '
       'and deduplicates the results, verifies metadata field by field, and downloads official publisher PDFs through a '
       'dedicated browser, checking each PDF\'s identity. Outputs are candidates with sources, a match report, RIS or BibTeX '
       'export, checked PDFs, and items that need attention.</desc>\n'
       f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>\n{defs}\n' + "\n".join(out) + "\n</svg>\n")
args.output.write_text(svg, encoding="utf-8")
args.output.with_suffix(".html").write_text(
    '<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:#fff}svg{display:block}</style>' + svg,
    encoding="utf-8")
print(args.output)
