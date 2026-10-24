"""Recolor the preview palette of extracted PIC PNGs (pixel indices are never touched).

    python tools/setpal.py list                      # names of all palettes found in the game
    python tools/setpal.py swatches                  # write ASSETS/graphics/palettes/*.png swatch sheets
    python tools/setpal.py STAR005 PIC000#3          # recolor one PIC directory
    python tools/setpal.py all [auto|<palette>]      # recolor every PIC directory ('auto' = built-in rule, the default)
The palette name is remembered in pic.json ('preview_palette') and is also what non-indexed PNGs are re-quantised to by build.py.
"""
import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import palsel
from PIL import Image

DEFAULT = 'auto'

def v8(p6): return bytes((v << 2) | (v >> 4) for v in p6[:768])

def by_name():
    return palsel.named_palettes()

def recolor_dir(d, name, pals):
    '''name = palette name or "auto" (number based default). Entries that carry (possibly partial) palettes overlay it.'''
    import picfile
    meta = json.load(open(os.path.join(d, 'pic.json')))
    num = int(os.path.basename(d)[4:7])
    if name == 'auto': name = palsel.default_name(num)
    base = pals[name]
    ents = [dict(pal=bytes.fromhex(m['pal']) if m.get('pal') else None, palfirst=m['palfirst']) for m in meta['entries']]
    eff = picfile.effective_palettes(ents, base)
    for png in sorted(glob.glob(os.path.join(d, '*.png'))):
        idx = int(os.path.basename(png)[:3])
        im = Image.open(png); im.putpalette(v8(eff[idx])); im.save(png)
    meta['preview_palette'] = name; meta['preview_pal'] = base.hex()
    json.dump(meta, open(os.path.join(d, 'pic.json'), 'w'), indent=1)

if __name__ == '__main__':
    pals = by_name()
    a = sys.argv[1:]
    if not a or a[0] == 'list':
        for n in sorted(pals): print(n)
    elif a[0] == 'swatches':
        out = assets('graphics', 'palettes'); os.makedirs(out, exist_ok=True)
        for n, p in pals.items():
            im = Image.new('P', (16, 16)); im.putdata(list(range(256))); im.putpalette(v8(p)); im = im.resize((128, 128), Image.NEAREST)
            im.save(os.path.join(out, n.replace('#', '_') + '.png'))
        print(len(pals), 'swatches ->', out)
    else:
        target, name = a[0], (a[1] if len(a) > 1 else DEFAULT)
        dirs = sorted(glob.glob(assets('graphics', 'pic', 'STAR*'))) if target == 'all' else [assets('graphics', 'pic', target)]
        for d in dirs:
            recolor_dir(d, name, pals)
        print('recolored', len(dirs), 'dir(s) with', name)
