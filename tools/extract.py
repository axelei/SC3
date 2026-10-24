"""Extract all translatable assets from ORIGINAL into ASSETS (ORIGINAL is never written)."""
import os, sys, json, glob, struct, argparse, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import sc3str, picfile, vocfile, fntfile, textcodec, exestr
from PIL import Image

def vga8(pal6):  # 6-bit VGA -> 8-bit (exactly invertible via >>2)
    return bytes((v << 2) | (v >> 4) for v in pal6)

# ---------------------------------------------------------------- text
def extract_text(man):
    S = sc3str.decode_all(orig('SC3STR.DAT'))
    lines = ['%04d|%s' % (i, textcodec.to_text(s, {})) for i, s in enumerate(S)]
    ensure(assets('text', 'x'))
    for p in (assets('text', 'SC3STR.txt'), assets('text', 'ref', 'SC3STR.en.txt')):
        ensure(p); open(p, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    man['text/SC3STR.txt'] = sha1(('\n'.join(lines) + '\n').encode())
    print('SC3STR: %d strings' % len(S))
    strings = exestr.find_strings(orig('SC3.EXE'))
    tr, te = exestr.split(strings)
    NL = chr(10); BS = chr(92)
    head = ('; SC3.EXE strings.  Format: <offset-in-data-object hex>|<text>.  Edit the text after the bar; keep every % code' + NL +
            '; (%s %d ...) in the same order.  Escapes: ' + BS + 'n newline, ' + BS + 't tab, ' + BS + BS + ' backslash.  Lines starting with ; are ignored.' + NL)
    body = exestr.fmt(tr)
    tech = '; Technical strings of SC3.EXE (file names, debug/config formats). Do NOT translate; build ignores this file.' + NL + exestr.fmt(te)
    for p, t in ((assets('text', 'SC3EXE.txt'), head + body), (assets('text', 'ref', 'SC3EXE.en.txt'), head + body),
                 (assets('text', 'SC3EXE.technical.txt'), tech)):
        ensure(p); open(p, 'w', encoding='utf-8', newline=NL).write(t)
    print('SC3EXE: %d translatable strings (+%d technical)' % (len(tr), len(te)))

# ---------------------------------------------------------------- pictures
STD_PAL = None
def std_palette():
    '''standard game palette: palette #3 of STAR000.PIC (renders ships/planets/sprites correctly; most PIC files carry no palette)'''
    global STD_PAL
    if STD_PAL is None:
        STD_PAL = [e['pal'] for e in picfile.parse(open(orig('STAR000.PIC'), 'rb').read()) if e['pal']][3]
    return STD_PAL

def _save_pic(args):
    name, = args
    data = open(orig(name), 'rb').read()
    ents = picfile.parse(data)
    base = name[:-4]
    outdir = assets('graphics', 'pic', base); os.makedirs(outdir, exist_ok=True)
    meta = []; curpal = None; hashes = {}
    for e in ents:
        if e['pal']: curpal = e['pal']
        m = dict(index=e['index'], key=e['key'], haspal=e['haspal'], x=e['x'], y=e['y'], w=e['w'], h=e['h'], rsv=e['rsv'], palfirst=e['palfirst'])
        if e['pal']: m['pal'] = e['pal'].hex()
        px = picfile.pixels(e)
        if px:
            im = Image.frombytes('P', (e['w'], e['h']), px)
            pal = vga8(curpal) if curpal else vga8(std_palette())
            im.putpalette(pal)
            fn = os.path.join(outdir, '%03d.png' % e['index']); im.save(fn, optimize=False)
            hashes[e['index']] = sha1(px)
        meta.append(m)
    json.dump(dict(file=name, entries=meta, pixel_sha1=hashes, preview_palette=('own' if any(e['pal'] for e in ents) else 'PIC000#3'),
                   preview_pal=std_palette().hex()), open(os.path.join(outdir, 'pic.json'), 'w'), indent=1)
    return base, len(ents)

def extract_pics(man, procs):
    files = sorted(os.path.basename(p) for p in glob.glob(orig('*.PIC')))
    with mp.Pool(procs) as pool:
        for base, n in pool.imap_unordered(_save_pic, [(f,) for f in files]): print('PIC', base, n, flush=True)
    import setpal; pals = setpal.by_name()
    for d in sorted(glob.glob(assets('graphics', 'pic', 'STAR*'))): setpal.recolor_dir(d, 'auto', pals)
    print('preview palettes assigned (see tools/setpal.py)')

# ---------------------------------------------------------------- voices
def _save_wav(args):
    slot, = args
    a = vocfile.Archive(orig('STAR001.VOC'))
    w = a.wav(slot)
    p = assets('voices', 'V%04d.wav' % slot)
    open(p, 'wb').write(w)
    return slot, sha1(w)

def extract_voices(man, procs):
    a = vocfile.Archive(orig('STAR001.VOC')); slots = a.slots(); a.f.close()
    os.makedirs(assets('voices'), exist_ok=True)
    h = {}
    with mp.Pool(procs) as pool:
        for k, (slot, s) in enumerate(pool.imap_unordered(_save_wav, [(s,) for s in slots], chunksize=8)):
            h[slot] = s
            if k % 200 == 0: print('VOC', k, '/', len(slots), flush=True)
    json.dump({'%04d' % k: v for k, v in sorted(h.items())}, open(assets('voices', 'voices.json'), 'w'), indent=0)
    print('voices:', len(h))

# ---------------------------------------------------------------- fonts
def font_to_png(f, path, cols=16):
    n = f.last - f.first + 1
    cw = f.bpr * 8; ch = f.height
    rows = (n + cols - 1) // cols
    im = Image.new('P', (cols * cw, rows * ch), 0); im.putpalette([255, 255, 255, 0, 0, 0] + [0] * 762)
    for i in range(n):
        gr = f.glyph_rows(f.first + i)
        for y, row in enumerate(gr):
            for x, v in enumerate(row):
                if v: im.putpixel(((i % cols) * cw + x, (i // cols) * ch + y), 1)
    im.save(path)

def extract_fonts(man):
    """Fonts are exported already extended to codes 0x80..0xFF with composed Spanish glyphs (see charmap.json)."""
    import fonttool
    outd = assets('graphics', 'fonts'); os.makedirs(outd, exist_ok=True)
    for p in sorted(glob.glob(orig('*.FNT'))):
        name = os.path.basename(p)[:-4]
        f = fntfile.Font(open(p, 'rb').read())
        fonttool.extend(f)
        font_to_png(f, os.path.join(outd, name + '.png'))
        json.dump(dict(file=os.path.basename(p), first=f.first, last=f.last, bpr=f.bpr, height=f.height, spacing=f.spacing,
                       wflag=f.wflag, kflag=f.kflag, unk=f.unk, ver=f.ver, ver2=f.ver2, cols=16,
                       widths=f.widths, kern=f.kern, tail=f.tail.hex()), open(os.path.join(outd, name + '.json'), 'w'), indent=1)
        print('FNT', name)
    json.dump({ch: code for ch, code in fonttool.LATIN1.items()}, open(assets('charmap.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('what', nargs='*', default=['text', 'fonts', 'pics', 'voices']); ap.add_argument('-j', type=int, default=8)
    a = ap.parse_args(); man = load_manifest()
    for w in a.what:
        if w == 'text': extract_text(man)
        elif w == 'fonts': extract_fonts(man)
        elif w == 'pics': extract_pics(man, a.j)
        elif w == 'voices': extract_voices(man, a.j)
    save_manifest(man)
