#!/usr/bin/env python3
"""Saturday 21 November 2026 - the world's news on one broadsheet page.

A table-driven page builder: the day's stories sit in the LEDGER section
and three small engines (cards, strips, briefs) lay them out. Artwork is
flat PIL line-and-fill scenes on cream newsprint. Build-time only: the
submitted program (main.py) copies the finished entry.png unchanged.
"""
import math

from PIL import Image, ImageDraw, ImageFont

PAGE = 1024
EDGE = 36                       # outer margin
SPAN = PAGE - 2 * EDGE          # usable width

CREAM = (248, 243, 226)
CREAM_DK = (239, 231, 205)
BLACK = (22, 20, 17)
GREY = (96, 90, 76)
CRIMSON = (172, 30, 44)
NAVY = (30, 76, 138)
PINE = (13, 112, 108)
OCHRE = (172, 118, 20)
MOSS = (48, 108, 56)
PLUM = (98, 64, 138)
WHITE = (255, 255, 255)

REGION_INK = {
    "EUROPE": CRIMSON, "ASIA": OCHRE, "AMERICAS": NAVY,
    "MIDDLE EAST": PINE, "AFRICA": MOSS, "OCEANIA": PLUM,
}

FONT_DIR = "/usr/share/fonts/truetype/liberation/"
SERIF = FONT_DIR + "LiberationSerif-Bold.ttf"
SERIF_IT = FONT_DIR + "LiberationSerif-BoldItalic.ttf"
SANS = FONT_DIR + "LiberationSans-Regular.ttf"
SANS_B = FONT_DIR + "LiberationSans-Bold.ttf"


def F(path, size):
    return ImageFont.truetype(path, size)


def wrap_text(d, text, fnt, width):
    """Word-wrap to a pixel width, newspaper style."""
    out, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if d.textlength(trial, font=fnt) <= width:
            line = trial
        else:
            if line:
                out.append(line)
            line = word
    if line:
        out.append(line)
    return out


def one_line(d, text, fnt, width):
    """Force a single line, cutting with an ellipsis when needed."""
    if d.textlength(text, font=fnt) <= width:
        return text
    while text and d.textlength(text + "…", font=fnt) > width:
        text = text.rsplit(" ", 1)[0] if " " in text else text[:-1]
    return text + "…"


# ------------------------------------------------------------------ scenes
def scene(d, kind, x, y, w, h, ink):
    """One small flat scene per story, drawn inside box (x, y, w, h)."""
    cx, cy = x + w // 2, y + h // 2
    if kind == "bases":                        # two flag poles, flame between
        for fx in (x + 26, x + w - 26):
            d.line([fx, y + 10, fx, y + h - 12], fill=BLACK, width=3)
            d.polygon([fx, y + 10, fx + 18, y + 16, fx, y + 22], fill=ink)
        d.polygon([cx, y + 18, cx - 10, cy + 8, cx - 3, cy + 2, cx, cy + 16,
                   cx + 4, cy + 2, cx + 11, cy + 10], fill=CRIMSON)
        d.rectangle([x + 10, y + h - 12, x + w - 10, y + h - 6], fill=BLACK)
    elif kind == "missile":                    # falling missile, rooftops
        d.polygon([x + w - 26, y + 8, x + w - 8, y + 24, x + w - 30, y + 30],
                  fill=BLACK)
        d.line([x + w - 26, y + 24, x + 34, y + h - 20], fill=CRIMSON, width=4)
        for i in range(3):
            bx = x + 14 + i * (w // 3)
            d.rectangle([bx, y + h - 18, bx + 22, y + h - 6], fill=ink)
            d.polygon([bx, y + h - 18, bx + 11, y + h - 28, bx + 22, y + h - 18],
                      fill=ink)
    elif kind == "chart-down":                 # plunging line, arrow head
        d.line([x + 10, y + h - 12, x + w - 10, y + h - 12], fill=BLACK, width=3)
        pts = [(x + 14, y + 14), (x + w // 3, y + h // 3),
               (x + w // 2, y + h - 42), (x + w - 16, y + h - 18)]
        d.line(pts, fill=CRIMSON, width=5)
        d.polygon([pts[-1], (pts[-1][0] - 14, pts[-1][1] - 2),
                   (pts[-1][0] - 2, pts[-1][1] - 14)], fill=CRIMSON)
        for px, py in pts[:3]:
            d.ellipse([px - 4, py - 4, px + 4, py + 4], fill=CRIMSON)
    elif kind == "cuffs":                      # two linked rings
        r = min(w, h) // 4
        for ccx in (cx - r, cx + r):
            d.ellipse([ccx - r, cy - r, ccx + r, cy + r], outline=BLACK, width=5)
        d.rectangle([cx - 8, cy - r - 8, cx + 8, cy - r + 2], fill=ink)
    elif kind == "handshake":                  # two sleeves, clasped hands
        d.polygon([x + 8, y + 12, cx - 6, cy + 6, x + 30, y + h - 14,
                   x + 8, y + h - 20], fill=NAVY)
        d.polygon([x + w - 8, y + 12, cx + 6, cy + 6, x + w - 30, y + h - 14,
                   x + w - 8, y + h - 20], fill=OCHRE)
        d.ellipse([cx - 13, cy - 2, cx + 13, cy + 22], fill=ink)
    elif kind == "globe":                      # wireframe earth
        r = min(w, h) // 2 - 8
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=NAVY, width=4)
        d.ellipse([cx - r // 3, cy - r, cx + r // 3, cy + r], outline=NAVY,
                  width=2)
        d.line([cx - r, cy, cx + r, cy], fill=NAVY, width=2)
        d.line([cx, cy - r, cx, cy + r], fill=NAVY, width=2)
    elif kind == "tanker":                     # hull, funnel, waves, flare
        d.polygon([x + 12, cy + 4, x + w - 12, cy + 4, x + w - 28, cy + 24,
                   x + 28, cy + 24], fill=BLACK)
        d.rectangle([cx - 14, cy - 18, cx + 14, cy + 4], fill=ink)
        d.polygon([x + w - 30, y + 8, x + w - 22, y + 22, x + w - 38, y + 22],
                  fill=CRIMSON)
        for i in range(3):
            wx = x + 12 + i * (w // 3)
            d.arc([wx, cy + 28, wx + 26, cy + 42], 0, 180, fill=NAVY, width=3)
    elif kind == "summit":                     # three pennants over a table
        for i, c in enumerate((CRIMSON, OCHRE, NAVY)):
            fx = x + 18 + i * (w - 36) // 2
            d.line([fx, y + 8, fx, y + h - 16], fill=BLACK, width=3)
            d.polygon([fx, y + 8, fx + 20, y + 14, fx, y + 20], fill=c)
        d.rectangle([x + 8, y + h - 14, x + w - 8, y + h - 8], fill=BLACK)
    else:                                      # "rays": starburst fallback
        for a in range(0, 360, 30):
            rad = math.radians(a)
            d.line([cx, cy, cx + int(30 * math.cos(rad)),
                    cy + int(30 * math.sin(rad))], fill=ink, width=4)
        d.ellipse([cx - 11, cy - 11, cx + 11, cy + 11], fill=ink)


# ------------------------------------------------------------------- cards
def number_disc(d, x, y, n):
    d.ellipse([x, y, x + 25, y + 25], fill=CRIMSON)
    d.text((x + 12.5, y + 12.5), str(n), font=F(SANS_B, 14), fill=WHITE,
           anchor="mm")


def story_card(d, st, x, y, w, h, tier, n):
    d.rectangle([x, y, x + w, y + h], fill=WHITE, outline=BLACK, width=2)
    ink = REGION_INK[st["region"]]
    d.rectangle([x, y, x + w, y + 5], fill=ink)
    if tier == "lead":
        scene(d, st["art"], x + 8, y + 12, w - 16, 94, ink)
        ty = y + 112
    elif tier == "mid":
        scene(d, st["art"], x + 8, y + 10, w - 16, 60, ink)
        ty = y + 76
    else:                                      # small card: the big figure
        d.text((x + w / 2, y + 27), st["stat"], font=F(SERIF, 32), fill=ink,
               anchor="mm")
        ty = y + 52
    number_disc(d, x + 8, ty, n)
    kx = x + 40
    d.text((kx, ty + 3), st["region"], font=F(SANS_B, 11), fill=ink)
    if tier == "small":
        print_block(d, st["headline"], x + 9, ty + 22, w - 18,
                    F(SERIF, 14), BLACK, 15, limit=2)
        return
    d.text((kx, ty + 16), st.get("src", ""), font=F(SANS, 9), fill=GREY)
    hsize, hstep = (19, 21) if tier == "lead" else (15, 17)
    hy = print_block(d, st["headline"], x + 9, ty + 30, w - 18,
                     F(SERIF, hsize), BLACK, hstep, limit=3)
    bsize = 11.5 if tier == "lead" else 10.5
    print_block(d, st["body"], x + 9, hy + 2, w - 18, F(SANS, bsize),
                GREY, 14, limit=3 if tier == "lead" else 2)


def print_block(d, text, x, y, width, fnt, fill, step, limit):
    """Set a wrapped block of text; return the y just past its last line."""
    for line in wrap_text(d, text, fnt, width)[:limit]:
        d.text((x, y), line, font=fnt, fill=fill)
        y += step
    return y


# ------------------------------------------------------------------ ledger
FIGURES = [  # (figure, caption) - Saturday in six numbers
    ("2", "US bases in Bahrain Iran says its Guards struck"),
    ("2", "killed as a missile hits Kryvyi Rih, Zelensky's home town"),
    ("11", "dead in Sinaloa violence after the cartel arrest"),
    ("98.5%", "of EU tariffs the Indonesia trade deal removes"),
    ("$1tn", "the Gulf states' estimated losses from the Iran war"),
    ("-10%", "Wall Street's slide into correction in the AI sell-off"),
]
REGION_TALLY = [("EUROPE", 10), ("AMERICAS", 11), ("MIDDLE EAST", 6),
                ("ASIA", 5), ("AFRICA", 3), ("OCEANIA", 1)]
LEADS = [
    {"region": "MIDDLE EAST", "art": "bases", "src": "Al Jazeera",
     "headline": "Iran strikes US bases in Bahrain",
     "body": "The Revolutionary Guards say they hit al-Riffa and Awali; "
             "Manama reports a fire at a civilian industrial plant."},
    {"region": "EUROPE", "art": "missile", "src": "OneTurn",
     "headline": "Missile hits Zelensky's home town",
     "body": "A Russian ballistic missile struck central Kryvyi Rih, "
             "killing two people and wounding dozens on Saturday."},
    {"region": "AMERICAS", "art": "chart-down", "src": "UPI",
     "headline": "AI sell-off tips Wall Street into correction",
     "body": "The S&P 500 and Dow enter correction and the Nasdaq wipes "
             "out its 2026 gains as Anthropic's IPO stumbles."},
]
MIDS = [
    {"region": "AMERICAS", "art": "cuffs", "src": "BBC",
     "headline": "Mexico seizes FBI most-wanted cartel boss",
     "body": "Seized in Guasave; the violence that followed kills 11."},
    {"region": "ASIA", "art": "handshake", "src": "France 24",
     "headline": "EU and Indonesia sign their trade deal",
     "body": "Brussels signing ends ten years of talks; 98.5% of tariffs go."},
    {"region": "EUROPE", "art": "globe", "src": "OneTurn",
     "headline": "COP31 deadlocked over fossil fuels",
     "body": "Phase-out fight leaves Antalya talks stuck on the final text."},
    {"region": "MIDDLE EAST", "art": "tanker", "src": "UKMTO",
     "headline": "Two tankers hit near the Hormuz strait",
     "body": "Two tanker incidents logged near Oman; Tehran blames a mine."},
    {"region": "ASIA", "art": "summit", "src": "BBC",
     "headline": "Shenzhen fallout: Trump defends Putin",
     "body": "Trump backs Putin ties; Zelensky calls him 'a killer'."},
]
SMALLS = [
    {"region": "EUROPE", "stat": "EXPELLED",
     "headline": "Denmark expels Russian envoy over rapper plot"},
    {"region": "AMERICAS", "stat": "6 WEEKS",
     "headline": "AI-aided Riemann proof claimed at Anthropic"},
    {"region": "ASIA", "stat": "UNSC",
     "headline": "France seeks UN action on Myanmar ruling"},
    {"region": "MIDDLE EAST", "stat": "HODEIDAH",
     "headline": "Houthis hit Saudi Arabia after Hodeidah strike"},
    {"region": "AMERICAS", "stat": "BACTERIA",
     "headline": "Bacteria mosquitoes cut child dengue in Brazil"},
]
BRIEFS = [
    (14, "EUROPE", "CERN reports first evidence of an ultra-rare particle decay"),
    (15, "EUROPE", "French officers sentenced over the Zecler beating in Paris"),
    (16, "AMERICAS", "Man convicted of starting the 2025 Palisades fire in LA"),
    (17, "AMERICAS", "FBI probes apparent hack of its criminal-justice database"),
    (18, "AMERICAS", "Rackspace breach exposes customers' Kubernetes secrets"),
    (19, "EUROPE", "Finland probes suspected Russian helicopter airspace breach"),
    (20, "MIDDLE EAST", "Fire at Basra power station kills four, injures 35"),
    (21, "MIDDLE EAST", "Lebanon's president demands Israel quit the south"),
    (22, "AFRICA", "Nigeria recovers 24 bodies after a boat capsize"),
    (23, "AFRICA", "ANC fights to hold on to South Africa's big cities"),
    (24, "AFRICA", "Chad closes its border with Sudan"),
    (25, "ASIA", "Nepal's PM Shah makes his first visit to India"),
    (26, "ASIA", "Manila hosts Quad, ASEAN-India and East Asia summits"),
    (27, "EUROPE", "EU floats a €1.78tn budget with a Big Tech tax"),
    (28, "EUROPE", "Sweden and France hold first joint nuclear drill"),
    (29, "EUROPE", "Geneva talks keep work on 'killer robot' rules alive"),
    (30, "AMERICAS", "Bolsonaro in intensive care with bowel obstruction"),
    (31, "AMERICAS", "Trump opens the Pacific seabed to deep-sea mining"),
    (32, "AMERICAS", "New York's Mamdani vows to close Rikers by 2032"),
    (33, "AMERICAS", "US declassifies more UFO footage from the Middle East"),
    (34, "MIDDLE EAST", "New fossil carnivore unearthed in the Emirates"),
    (35, "EUROPE", "Norway fells Trafalgar Square's Christmas tree"),
    (36, "OCEANIA", "Australia: former MP Fred Nile dies at 92"),
]
DATE_CHECK = ("Checked before printing: the missiles that fell in Poland "
              "and Cyclone Akvan's landfall belong to Friday 20 November, "
              "so Poland appears here only as Saturday's NATO fallout; "
              "the Peru quake reached Sunday's wires and is left out. "
              "Every story on this page is dated Saturday 21 November 2026.")
DECK = ("Iran hits Bahrain, a missile in Zelensky's home town, Wall "
        "Street's AI rout: one Saturday.")


# -------------------------------------------------------------------- page
def masthead(d):
    """Kicker row, the big serif date, and the deck line under it."""
    d.text((EDGE, 22), "THE DAILY WORLD · THE WORLD IN ONE DAY",
           font=F(SANS_B, 13), fill=CRIMSON)
    right = "36 STORIES · 6 REGIONS · EVERY ONE DATED SATURDAY 21 NOVEMBER 2026"
    d.text((PAGE - EDGE, 22), right, font=F(SANS_B, 13), fill=BLACK,
           anchor="ra")
    d.line([EDGE, 42, PAGE - EDGE, 42], fill=BLACK, width=3)
    d.text((PAGE / 2, 50), "Saturday 21 November 2026", font=F(SERIF, 57),
           fill=BLACK, anchor="ma")
    d.line([EDGE, 116, PAGE - EDGE, 116], fill=BLACK, width=1)
    d.text((PAGE / 2, 122), DECK, font=F(SERIF_IT, 19), fill=GREY, anchor="ma")


def figures_strip(d, top):
    """Six numbered facts in a ruled, shaded band."""
    cell = SPAN / 6
    d.rectangle([EDGE, top, PAGE - EDGE, top + 58], fill=CREAM_DK,
                outline=BLACK, width=2)
    for i, (val, cap) in enumerate(FIGURES):
        cx = EDGE + i * cell
        if i:
            d.line([cx, top, cx, top + 58], fill=BLACK, width=1)
        d.text((cx + cell / 2, top + 6), val, font=F(SERIF, 25),
               fill=CRIMSON, anchor="ma")
        lines = wrap_text(d, cap, F(SANS, 9.5), cell - 12)[:2]
        for j, line in enumerate(lines):
            d.text((cx + cell / 2, top + 36 + j * 11), line,
                   font=F(SANS, 9.5), fill=GREY, anchor="ma")


def tally_bar(d, top):
    """Black band naming each region and how many stories it holds."""
    d.rectangle([EDGE, top, PAGE - EDGE, top + 28], fill=BLACK)
    label = "   ·   ".join(f"{name} {n}" for name, n in REGION_TALLY)
    d.text((PAGE / 2, top + 6), label, font=F(SANS_B, 13.5), fill=WHITE,
           anchor="ma")


def briefs_block(d, top, gap):
    """The rest of the day: numbered one-liners in three columns."""
    d.text((EDGE, top), "ALSO ON SATURDAY 21 NOVEMBER — THE REST OF THE DAY",
           font=F(SANS_B, 13), fill=BLACK)
    d.line([EDGE, top + 20, PAGE - EDGE, top + 20], fill=BLACK, width=1)
    col_w = (SPAN - 2 * gap) / 3
    bf = F(SANS, 10.5)
    per_col = (len(BRIEFS) + 2) // 3
    for i, (n, region, text) in enumerate(BRIEFS):
        col, row = divmod(i, per_col)
        bx = EDGE + col * (col_w + gap)
        by = top + 26 + row * 14.8
        d.text((bx, by), f"{n}.", font=F(SANS_B, 10.5), fill=CRIMSON)
        d.text((bx + 22, by), one_line(d, text, bf, col_w - 24), font=bf,
               fill=BLACK)


def date_check_box(d):
    """Red-ruled strip recording what was deliberately left out, and why."""
    d.rectangle([EDGE, 954, PAGE - EDGE, 998], outline=CRIMSON, width=2)
    d.text((EDGE + 10, 960), "DATE CHECK", font=F(SANS_B, 12), fill=CRIMSON)
    lines = wrap_text(d, DATE_CHECK, F(SANS, 10.5), SPAN - 130)[:2]
    for j, line in enumerate(lines):
        d.text((EDGE + 108, 961 + j * 14), line, font=F(SANS, 10.5),
               fill=BLACK)
    d.text((PAGE - EDGE, 1004), "Sources credited per panel · Original artwork",
           font=F(SANS, 9.5), fill=GREY, anchor="ra")


def render_page():
    img = Image.new("RGB", (PAGE, PAGE), CREAM)
    d = ImageDraw.Draw(img)
    masthead(d)
    figures_strip(d, 148)
    tally_bar(d, 214)
    gap = 10
    lead_w = (SPAN - 2 * gap) / 3
    for i, st in enumerate(LEADS):
        story_card(d, st, EDGE + i * (lead_w + gap), 252, lead_w, 234,
                   "lead", i + 1)
    mid_w = (SPAN - 4 * gap) / 5
    for i, st in enumerate(MIDS):
        story_card(d, st, EDGE + i * (mid_w + gap), 496, mid_w, 178,
                   "mid", i + 4)
    for i, st in enumerate(SMALLS):
        story_card(d, st, EDGE + i * (mid_w + gap), 684, mid_w, 114,
                   "small", i + 9)
    briefs_block(d, 810, gap)
    date_check_box(d)
    img.save("entry.png")
    print("wrote entry.png")


if __name__ == "__main__":
    render_page()
