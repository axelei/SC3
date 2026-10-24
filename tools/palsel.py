"""Choose a display palette for PIC files that carry none: among all palettes found in the game (Q files + STAR000.PIC),
pick the one that makes the images smoothest (minimal colour difference between neighbouring pixels)."""
import sys, os, struct, glob, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import picfile
from common import orig

def candidates():
    c = {}
    for e in picfile.parse(open(orig('STAR000.PIC'), 'rb').read()):
        if e['pal']: c.setdefault(bytes(e['pal']), 'PIC000#%d' % e['index'])
    for f in sorted(glob.glob(orig('*.Q'))):
        d = open(f, 'rb').read(); p = 26
        while p + 6 <= len(d):
            t, sz = struct.unpack('<HI', d[p:p+6])
            if t == 1 and sz == 768: c.setdefault(d[p+6:p+6+sz], os.path.basename(f))
            p += 6 + sz
    return c

def pair_counts(ents, maxpix=400000):
    M = np.zeros((256, 256), np.float64); n = 0
    for e in ents:
        if not e['size'] or e['w'] < 4 or e['h'] < 4: continue
        a = np.frombuffer(picfile.pixels(e), np.uint8).reshape(e['h'], e['w'])
        h = (a[:, :-1].ravel(), a[:, 1:].ravel()); v = (a[:-1].ravel(), a[1:].ravel())
        for x, y in (h, v):
            np.add.at(M, (x, y), 1); n += len(x)
        if n > maxpix: break
    return M

def best(M, cands):
    res = []
    for pal, name in cands.items():
        rgb = np.frombuffer(pal, np.uint8).reshape(256, 3).astype(np.float64) * 4
        D = np.abs(rgb[:, None, :] - rgb[None, :, :]).sum(2)
        res.append(((M * D).sum() / max(M.sum(), 1), name, pal))
    res.sort(key=lambda r: r[0])
    return res


def named_palettes():
    """{name: 768-byte 6-bit palette}: palettes stored in PIC files ('PICnnn#entry') and in Q files ('STARnnn.Q')."""
    out = {}
    for f in sorted(glob.glob(orig('*.PIC'))):
        for e in picfile.parse(open(f, 'rb').read()):
            if e['pal'] and len(e['pal']) == 768: out.setdefault('PIC%s#%d' % (os.path.basename(f)[4:7], e['index']), bytes(e['pal']))
    for pal, name in candidates().items():
        if name.endswith('.Q'): out.setdefault(name, pal)
    return out

def default_name(num, has_own=False):
    """default preview palette for a PIC file number: planets / colony / UI screens use the 'System UI' palette stored in STAR401.PIC"""
    if 700 <= num <= 703: return 'PIC715#21'      # colony facility sprites use the colony palettes stored in STAR715.PIC
    return 'PIC401#0' if 400 <= num <= 799 else 'PIC000#3'
