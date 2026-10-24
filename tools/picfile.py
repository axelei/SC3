"""STARnnn.PIC container.
u16 count; count * 20-byte entries:
   u32 offset, u32 size(compressed bytes of pixel data), u8 key, u8 haspal, u16 x, u16 y, u16 w, u16 h, u16 reserved
At `offset`: if haspal: {u16 first, u16 nbytes(768)} + palette (6-bit VGA RGB); then `size` bytes of pixel data.
Pixel data: raw if size == w*h, else LHA lh4 stream decoding to w*h bytes."""
import struct, sys
sys.path.insert(0, 'tools')
import lha

def parse(data):
    n = struct.unpack('<H', data[:2])[0]
    ents = []
    for i in range(n):
        e = data[2+20*i:22+20*i]
        off, size, key, haspal, x, y, w, h, rsv = struct.unpack('<IIBBHHHHH', e)
        pal = None; pos = off; first = 0
        if haspal:
            first, nb = struct.unpack('<HH', data[pos:pos+4]); pal = data[pos+4:pos+4+nb]; pos += 4 + nb
        raw = data[pos:pos+size]
        ents.append(dict(index=i, key=key, haspal=haspal, x=x, y=y, w=w, h=h, rsv=rsv, size=size,
                         palfirst=first, pal=pal, raw=raw))
    return ents

def pixels(e):
    w, h = e['w'], e['h']
    if w*h == 0 or e['size'] == 0: return b''
    if e['size'] == w*h: return e['raw']
    return lha.decode(e['raw'], w*h)

def build(ents, pix_list):
    """Rebuild PIC file. pix_list[i] = raw pixel bytes (uncompressed) or None for empty entries."""
    head = bytearray(struct.pack('<H', len(ents)))
    body = bytearray(); base = 2 + 20*len(ents)
    for e, px in zip(ents, pix_list):
        off = base + len(body)
        if e['haspal']:
            body += struct.pack('<HH', e['palfirst'], len(e['pal'])) + e['pal']
        px = px or b''
        body += px
        head += struct.pack('<IIBBHHHHH', off, len(px), e['key'], e['haspal'], e['x'], e['y'], e['w'], e['h'], e['rsv'])
    return bytes(head + body)


def build_raw(ents, blobs):
    """ents: entry dicts (key, haspal, palfirst, pal, x, y, w, h, rsv); blobs: stored pixel bytes per entry
    (compressed original bytes, or uncompressed w*h pixels)."""
    return build(ents, blobs)


def effective_palettes(ents, default):
    """Palette in force for every entry (preview/quantisation only; the game applies palettes from code).
    A palette block overwrites colours starting at byte `palfirst`.
    * files that contain PARTIAL blocks (STAR600, STAR800): partial blocks accumulate over the default palette and stay in
      force; FULL (768-byte) blocks are alternative palettes that apply to their own entry only;
    * other files: blocks apply sequentially; entries before the first block use the first block."""
    has_partial = any(e.get('pal') and len(e['pal']) < 768 for e in ents)
    cur = bytearray(default)
    out = []; started = False
    for e in ents:
        pal = e.get('pal')
        if pal and has_partial:
            if len(pal) < 768:
                cur[e['palfirst']:e['palfirst'] + len(pal)] = pal; out.append(bytes(cur))
            else:
                out.append(bytes(pal))
            continue
        if pal:
            cur[e['palfirst']:e['palfirst'] + len(pal)] = pal
            if not started:
                started = True
                for k in range(len(out)): out[k] = bytes(cur)   # leading entries share the first palette
        out.append(bytes(cur))
    return out
