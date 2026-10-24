"""Translator-facing text <-> game byte strings.

Editable files are UTF-8, one string per line:  <id>|<text>
Escapes: two backslashes = one backslash, backslash+xNN = raw byte NN.
Spanish characters are mapped through ASSETS/charmap.json (unicode char -> game byte code).
"""
import json, re, os
from common import assets

BS = chr(92)
_CM = None


def charmap():
    global _CM
    if _CM is None:
        p = assets('charmap.json')
        _CM = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}
    return _CM


def to_text(b, cm=None):
    """game bytes -> editable unicode line (inverse charmap applied when cm given)"""
    inv = {(v if isinstance(v, int) else ord(v)): k for k, v in (cm or {}).items()}
    out = []
    for c in b:
        if c in inv: out.append(inv[c])
        elif c == 92: out.append(BS + BS)
        elif c == 10: out.append(BS + 'n')
        elif c == 9: out.append(BS + 't')
        elif c < 32 or c > 126: out.append(BS + 'x%02x' % c)
        else: out.append(chr(c))
    t = ''.join(out)
    # leading/trailing spaces are significant (strings get concatenated): protect them from editors
    n = len(t) - len(t.rstrip(' '))
    if n: t = t[:len(t) - n] + (BS + 's') * n
    n = len(t) - len(t.lstrip(' '))
    if n: t = (BS + 's') * n + t[n:]
    return t


def to_bytes(t, cm=None):
    cm = cm if cm is not None else charmap()
    out = bytearray(); i = 0
    while i < len(t):
        ch = t[i]
        if ch == BS and i + 1 < len(t):
            if t[i + 1] == BS:
                out.append(92); i += 2; continue
            if t[i + 1] == 'n':
                out.append(10); i += 2; continue
            if t[i + 1] == 't':
                out.append(9); i += 2; continue
            if t[i + 1] == 's':
                out.append(32); i += 2; continue
            m = re.match(r'x([0-9a-fA-F]{2})', t[i + 1:i + 4])
            if m:
                out.append(int(m.group(1), 16)); i += 4; continue
        if ch in cm: out.append(cm[ch] if isinstance(cm[ch], int) else ord(cm[ch]))
        elif ord(ch) < 128: out.append(ord(ch))
        else: raise ValueError('character %r (U+%04X) has no mapping in charmap.json' % (ch, ord(ch)))
        i += 1
    return bytes(out)
