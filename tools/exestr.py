"""Translatable strings of SC3.EXE (data object). Strings are located through the LE fixup table: every fixup that
points into the data object at the start of a printable C string identifies a string (exact start, no guessing)."""
import os, re, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lefix, leimg, textcodec

TECH = re.compile(rb'AIL_|AIL\b|PLAYER%d|SC3[A-Z]|\.(INI|DAT|EXE|PIC|SAV|VOC|FNT|MDI|DIG|PIF|ICO|LOC)\b|%s%03d|^gw_|DOS/4G|DOS/16M|Rational'
                  rb'|^Result|^Corrupted|^[a-z_]+\(|^%[0-9a-z.]+$|^(rb|wb|r|w|ab)$'
                  rb'|^(DIAG|NOMASK|RBRN|QSF|TIMB|MOUSE|PRELOAD|PICDATA|QDATA|VOCDATA|SAVEDATA|SECTOR|CONFIG|MODE|STAR|FLEET|TWI|FNT|PIC|PLAYER\d?)$')

def find_strings(path):
    d, objs = leimg.load(path); data = objs[1]['data']
    fx = lefix.parse(path)
    targets = sorted({t for o, _, s, to, t in fx if to == 1 and t is not None and t < len(data)})
    out = []
    for t in targets:
        e = data.find(b'\0', t); s = data[t:e]
        if len(s) >= 2 and all(32 <= c < 127 or c in (9, 10) for c in s) and re.search(rb'[A-Za-z]', s):
            out.append((t, s))
    return out

def split(strings):
    tr = [(t, s) for t, s in strings if not TECH.search(s)]
    te = [(t, s) for t, s in strings if TECH.search(s)]
    return tr, te

def fmt(lst):
    return ''.join('%06x|%s\n' % (t, textcodec.to_text(s, {})) for t, s in lst)

def parse_lines(text):
    out = {}
    for ln, line in enumerate(text.split('\n'), 1):
        if not line.strip() or line.startswith(';'): continue
        off, _, body = line.partition('|')
        out[int(off, 16)] = body
    return out
