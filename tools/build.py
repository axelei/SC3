"""Build the Spanish game directory SC3E from ORIGINAL (read-only) + ASSETS (translated/edited assets).

    python tools/build.py [--no-copy] [--only text,exe,fonts,pics,voices]

Unchanged assets are carried over byte-for-byte from ORIGINAL; only edited ones are re-encoded.
"""
import os, sys, json, glob, shutil, struct, argparse, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import sc3str, picfile, vocfile, fntfile, textcodec, exestr, lepatch
from PIL import Image


def out_write(name, data):
    p = sc3e(name)
    if os.path.lexists(p): os.remove(p)          # never write through a (hard)link into ORIGINAL
    with open(p, 'wb') as f: f.write(data)


def read_lines(path, expect_prefix=None):
    return open(path, encoding='utf-8').read().split('\n')


# ------------------------------------------------------------------ copy base
BIG = ('.Q', '.PIC', '.VOC')

def copy_base():
    os.makedirs(SC3E, exist_ok=True)
    for f in sorted(os.listdir(ORIG)):
        src = orig(f); dst = sc3e(f)
        if os.path.lexists(dst): os.remove(dst)
        shutil.copyfile(src, dst)             # plain copies: ORIGINAL stays untouched, SC3E is independent


# ------------------------------------------------------------------ checks
import re
FMT = re.compile(r'%[-+ #0]*\d*(?:\.\d+)?[a-zA-Z%]')

def check_formats(ref_map, cur_map, label):
    '''warn when a translation changes the sequence of printf codes of the original string'''
    n = 0
    for k, r in ref_map.items():
        c = cur_map.get(k)
        if c is not None and c != r and FMT.findall(r) != FMT.findall(c):
            print('WARNING %s %s: printf codes differ: %s -> %s' % (label, k, FMT.findall(r), FMT.findall(c))); n += 1
    return n


# ------------------------------------------------------------------ text
def build_strings():
    cm = textcodec.charmap()
    cur = [l for l in read_lines(assets('text', 'SC3STR.txt')) if l.strip() != '']
    ref = [l for l in read_lines(assets('text', 'ref', 'SC3STR.en.txt')) if l.strip() != '']
    if cur == ref:
        print('SC3STR.DAT: unchanged'); return False
    check_formats({l.partition('|')[0]: l.partition('|')[2] for l in ref}, {l.partition('|')[0]: l.partition('|')[2] for l in cur}, 'SC3STR')
    if len(cur) != len(ref): raise SystemExit('SC3STR.txt has %d lines, expected %d' % (len(cur), len(ref)))
    strings = []
    for i, line in enumerate(cur):
        sid, _, body = line.partition('|')
        if int(sid) != i: raise SystemExit('SC3STR.txt line %d has id %s' % (i + 1, sid))
        try: strings.append(textcodec.to_bytes(body, cm))
        except ValueError as e: raise SystemExit('SC3STR.txt id %s: %s' % (sid, e))
    out_write('SC3STR.DAT', sc3str.build(strings, orig('SC3STR.DAT')))
    print('SC3STR.DAT: rebuilt (%d strings, %d changed)' % (len(strings), sum(a != b for a, b in zip(cur, ref))))
    return True


def build_exe():
    cm = textcodec.charmap()
    cur = exestr.parse_lines(open(assets('text', 'SC3EXE.txt'), encoding='utf-8').read())
    ref = exestr.parse_lines(open(assets('text', 'ref', 'SC3EXE.en.txt'), encoding='utf-8').read())
    check_formats(ref, cur, 'SC3EXE')
    new = {}
    for off, body in cur.items():
        if ref.get(off) == body: continue
        try: new[off] = textcodec.to_bytes(body, cm)
        except ValueError as e: raise SystemExit('SC3EXE.txt %06x: %s' % (off, e))
    if not new:
        print('SC3.EXE: unchanged'); return False
    exe = open(orig('SC3.EXE'), 'rb').read()
    out, changed, base3 = lepatch.relocate_strings(exe, new)
    out_write('SC3.EXE', out)
    print('SC3.EXE: %d strings relocated (%d fixups) -> object 3 @ %#x' % (len(new), changed, base3))
    return True


# ------------------------------------------------------------------ fonts
def png_to_glyphs(png, meta):
    im = Image.open(png).convert('P') if Image.open(png).mode != 'P' else Image.open(png)
    px = im.load(); cols = meta['cols']; bpr = meta['bpr']; H = meta['height']
    n = meta['last'] - meta['first'] + 1
    cw = bpr * 8
    out = []
    for i in range(n):
        rows = []
        for y in range(H):
            v = 0
            for x in range(cw):
                v = (v << 1) | (1 if px[(i % cols) * cw + x, (i // cols) * H + y] == 1 else 0)
            rows.append(v.to_bytes(bpr, 'big'))
        out.append(b''.join(rows))
    return out


def build_fonts():
    for jp in sorted(glob.glob(assets('graphics', 'fonts', '*.json'))):
        meta = json.load(open(jp)); name = os.path.basename(jp)[:-5]
        f = fntfile.Font(open(orig(meta['file']), 'rb').read())
        f.last = meta['last']; f.widths = meta['widths']; f.kern = meta['kern']; f.spacing = meta['spacing']
        f.glyphs = png_to_glyphs(assets('graphics', 'fonts', name + '.png'), meta)
        f.tail = bytes.fromhex(meta['tail'])
        out_write(meta['file'], f.to_bytes())
    print('fonts: rebuilt')


# ------------------------------------------------------------------ pictures
def vga6(pal8):
    return bytes(v >> 2 for v in pal8)


def png_pixels(path, w, h, palette6):
    im = Image.open(path)
    if im.mode != 'P':
        pi = Image.new('P', (1, 1)); pi.putpalette(bytes((v << 2) | (v >> 4) for v in palette6))
        im = im.convert('RGB').quantize(palette=pi, dither=Image.Dither.NONE)
    return im.size, im.tobytes()


def build_pics():
    changed_files = 0
    for d in sorted(glob.glob(assets('graphics', 'pic', 'STAR*'))):
        base = os.path.basename(d); meta = json.load(open(os.path.join(d, 'pic.json')))
        data = open(orig(meta['file']), 'rb').read()
        ents = picfile.parse(data)
        chunks = []; dirty = False
        effp = picfile.effective_palettes(ents, bytes.fromhex(meta.get('preview_pal', '00' * 768)))
        for e, m in zip(ents, meta['entries']):
            curpal = effp[e['index']]
            e2 = dict(e)
            for k in ('key', 'x', 'y', 'w', 'h', 'rsv', 'palfirst'): e2[k] = m[k]
            if 'pal' in m: e2['pal'] = bytes.fromhex(m['pal']); e2['haspal'] = e['haspal']
            if (e2['pal'] or b'') != (e['pal'] or b'') or any(e2[k] != e[k] for k in ('key', 'x', 'y', 'rsv', 'palfirst')): dirty = True
            png = os.path.join(d, '%03d.png' % e['index'])
            blob = e['raw']
            if os.path.exists(png):
                size, px = png_pixels(png, e2['w'], e2['h'], curpal)
                if sha1(px) != meta['pixel_sha1'].get(str(e['index'])) or size != (e['w'], e['h']):
                    e2['w'], e2['h'] = size
                    blob = px; dirty = True
            chunks.append((e2, blob))
        if dirty:
            out_write(meta['file'], picfile.build_raw([c[0] for c in chunks], [c[1] for c in chunks]))
            changed_files += 1
            print('PIC', base, 'rebuilt')
    print('pics: %d file(s) rebuilt' % changed_files)


# ------------------------------------------------------------------ voices
def build_voices():
    h = json.load(open(assets('voices', 'voices.json')))
    a = vocfile.Archive(orig('STAR001.VOC')); ents = {}; changed = 0
    for slot in a.slots():
        p = assets('voices', 'V%04d.wav' % slot)
        if not os.path.exists(p):
            raise SystemExit('missing %s (deleting a voice is not supported; keep the original)' % p)
        wb = open(p, 'rb').read()
        if sha1(wb) == h['%04d' % slot]:
            ents[slot] = a.raw_entry_bytes(slot)
        else:
            ents[slot] = vocfile.wav_to_entry(wb); changed += 1
    if not changed:
        print('STAR001.VOC: unchanged'); return False
    out_write('STAR001.VOC', vocfile.build(ents, a.n))
    print('STAR001.VOC: rebuilt (%d voices replaced)' % changed)
    return True


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='text,exe,fonts,pics,voices')
    ap.add_argument('--no-copy', action='store_true', help='keep the existing SC3E content, only re-run the selected steps')
    a = ap.parse_args(); steps = a.only.split(',')
    if not a.no_copy: copy_base()
    if 'text' in steps: build_strings()
    if 'exe' in steps: build_exe()
    if 'fonts' in steps: build_fonts()
    if 'pics' in steps: build_pics()
    if 'voices' in steps: build_voices()
    print('done ->', SC3E)
