"""Compose Spanish glyphs (accents, enye, inverted punctuation) for the SC3 bitmap fonts and extend them to codes 0x80..0xFF.

Glyph geometry of the 12-row fonts: capitals use rows 0..8, lowercase x-height rows 3..8, rows 9..11 are the descender
area.  Lowercase accents are drawn on rows 0..1; for accented capitals the whole glyph is lowered one row so a one-row
accent fits on row 0.  The 6-row 'tiny' font (STAR002) has no room for marks: accented letters use the base letter.
The result is only a starting point - glyph sheets in ASSETS/graphics/fonts can be redrawn freely.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# unicode char -> (base char, mark)
SPANISH = {
    'á': ('a', 'acute'), 'é': ('e', 'acute'), 'í': ('i', 'acute'), 'ó': ('o', 'acute'), 'ú': ('u', 'acute'),
    'Á': ('A', 'acute'), 'É': ('E', 'acute'), 'Í': ('I', 'acute'), 'Ó': ('O', 'acute'), 'Ú': ('U', 'acute'),
    'ñ': ('n', 'tilde'), 'Ñ': ('N', 'tilde'), 'ü': ('u', 'diaer'), 'Ü': ('U', 'diaer'),
    '¿': ('?', 'flip'), '¡': ('!', 'flip'),
}
LATIN1 = {ch: ord(ch.encode('latin-1')) for ch in SPANISH}


def _bbox(rows):
    xs = [x for r in rows for x, v in enumerate(r) if v]
    return (min(xs), max(xs)) if xs else (0, 0)


def compose(font, base, mark):
    """returns (rows, width) for the new glyph in `font`"""
    bc = ord(base)
    rows = [list(r) for r in font.glyph_rows(bc)]
    w = font.width(bc)
    H = font.height
    if H < 9 or font.bpr < 2:                    # tiny font: no room for marks
        return rows, w
    if mark == 'flip':                           # rotate the 9-row cell by 180 degrees (vertical flip + mirror)
        x0, x1 = _bbox(rows)
        body = []
        for r in rows[:9][::-1]:
            nr = [0] * len(r)
            for x, v in enumerate(r):
                if v and 0 <= x0 + x1 - x < len(r): nr[x0 + x1 - x] = 1
            body.append(nr)
        return body + [[0] * len(rows[0]) for _ in range(H - 9)], w
    cap = base.isupper()
    x0, x1 = _bbox(rows)
    cx = (x0 + x1) // 2
    if cap:                                      # lower by one row, accent on row 0
        rows = [[0] * len(rows[0])] + rows[:H - 1]
    if base == 'i':                              # drop the dot, accent takes its place
        for y in range(0, 3): rows[y] = [0] * len(rows[y])

    def put(y, x):
        if 0 <= y < H and 0 <= x < len(rows[0]): rows[y][x] = 1
    if mark == 'acute':
        if cap: put(0, cx + 1); put(0, cx + 2)
        else: put(0, cx + 1); put(1, cx)
    elif mark == 'tilde':
        if cap: put(0, cx - 1); put(0, cx); put(0, cx + 2)
        else: put(0, cx); put(0, cx + 2); put(1, cx - 1); put(1, cx + 1)
    elif mark == 'diaer':
        if cap: put(0, cx - 1); put(0, cx + 1)
        else: put(0, cx - 1); put(0, cx + 1)
    return rows, w


def rows_to_bytes(rows, bpr):
    out = bytearray()
    for r in rows:
        v = 0
        for x in range(bpr * 8): v = (v << 1) | (r[x] if x < len(r) else 0)
        out += v.to_bytes(bpr, 'big')
    return bytes(out)


def extend(font, mapping=LATIN1, last=0xFF, default_width=None, compose_new=True):
    """Extend `font` to cover codes up to `last`; add composed Spanish glyphs at mapping[ch] codes."""
    if last > font.last:
        gs = font.bpr * font.height
        for c in range(font.last + 1, last + 1):
            font.glyphs.append(bytes(gs))
            if font.widths is not None: font.widths.append(default_width if default_width is not None else 6)
        if font.kern is not None: font.kern += [0] * (last - font.last)
        font.last = last
    if compose_new:
        for ch, code in mapping.items():
            base, mark = SPANISH[ch]
            rows, w = compose(font, base, mark)
            font.glyphs[code - font.first] = rows_to_bytes(rows, font.bpr)
            if font.widths is not None: font.widths[code] = w
    return font
