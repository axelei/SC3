"""STARnnn.FNT bitmap fonts.
Header (10 bytes): ver, ver2, bytes_per_row, first, last, spacing, height, width_flag, kern_flag, unk
width table (last+1 bytes) present when width_flag (byte7) is negative (>=0x80); otherwise fixed width = width_flag.
kerning/bearing table (last+1 bytes) present when kern_flag (byte8) is negative.
glyph data: (last-first+1) glyphs, each height*bytes_per_row bytes, MSB = leftmost pixel."""
import struct

class Font:
    def __init__(self, data):
        h = data[:10]
        (self.ver, self.ver2, self.bpr, self.first, self.last, self.spacing, self.height, self.wflag, self.kflag, self.unk) = h
        p = 10; n = self.last + 1
        self.widths = None; self.kern = None
        if self.wflag >= 0x80: self.widths = list(data[p:p+n]); p += n
        if self.kflag >= 0x80: self.kern = list(data[p:p+n]); p += n
        ng = self.last - self.first + 1; gs = self.bpr * self.height
        self.glyphs = [data[p+i*gs:p+(i+1)*gs] for i in range(ng)]
        p += ng*gs
        self.tail = data[p:]
    def width(self, c):
        return self.widths[c] if self.widths else self.wflag
    def to_bytes(self):
        out = bytes([self.ver, self.ver2, self.bpr, self.first, self.last, self.spacing, self.height, self.wflag, self.kflag, self.unk])
        if self.widths: out += bytes(self.widths)
        if self.kern: out += bytes(self.kern)
        return out + b''.join(self.glyphs) + self.tail
    def glyph_rows(self, c):
        g = self.glyphs[c - self.first]
        rows = []
        for r in range(self.height):
            v = int.from_bytes(g[r*self.bpr:(r+1)*self.bpr], 'big')
            rows.append([(v >> (self.bpr*8-1-x)) & 1 for x in range(self.bpr*8)])
        return rows
