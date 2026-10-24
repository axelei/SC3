"""Star Control 3 voice sample codec (SC3.EXE func 0x78f80), ported from the original decoder.
Token stream:  b7=1  -> absolute level  cur=(b&0x7f)*2, emit 1 sample
               b6=1  -> run             emit cur (b&0x3f)+1 times
               else  -> delta block     row=b&0xf, mode=b&0x30 (0x10:1bit +7, 0x20:2bit +6, 0x30:4bit)
                         followed by `blocksz` (header type word, 0x20) samples packed LSB-first, delta=table[row][idx]
"""
import sys
sys.path.insert(0, 'tools')

def load_table(path='ORIGINAL/SC3.EXE'):
    import leimg
    d, objs = leimg.load(path)
    t = objs[1]['data'][0x3d8a8:0x3d8a8+256]
    return [b-256 if b > 127 else b for b in t]

TABLE = None
def table():
    global TABLE
    if TABLE is None: TABLE = load_table()
    return TABLE

def decode(src, blocksz=0x20):
    T = table()
    out = bytearray(); cur = 0x80; p = 0; n = len(src); bpp = 4
    while p < n:
        tok = src[p]; p += 1
        if tok & 0x80:
            cur = (tok & 0x7f) << 1; out.append(cur & 255)
        elif tok & 0x40:
            out += bytes([cur & 255]) * ((tok & 0x3f) + 1)
        else:
            row = tok & 0xf; base = row*16; mode = tok & 0x30
            if mode == 0x10: bpp = 1; base += 7
            elif mode == 0x20: bpp = 2; base += 6
            elif mode == 0x30: bpp = 4
            mask = (1 << bpp) - 1
            bitpos = 8; dcur = 0; dprev = 0; di = 0
            for _ in range(blocksz):
                if bitpos >= 8:
                    if p >= n: break
                    di = src[p]; p += 1; bitpos = 0
                dprev = dcur
                d = T[base + (di & mask)]
                cur += d
                if cur < 0: cur = 0
                elif cur > 255: cur = 255
                dcur = d
                if abs(d) == row + 1 and d == -dprev and out:
                    adj = (-dprev + (1 if d < 0 else 0)) >> 1
                    v = out[-1] + adj
                    out[-1] = 0 if v < 0 else 255 if v > 255 else v
                out.append(cur)
                di >>= bpp; bitpos += bpp
    return bytes(out)
