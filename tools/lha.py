"""LHA -lh4- (ar002) raw stream decoder used by Star Control 3 for PIC / Q / VOC payloads.
DICBIT=12 (4 KB window), MSB-first bit stream, no header, caller supplies the output size."""
THRESHOLD = 3; UCHAR_MAX = 255; CHAR_BIT = 8
NC = UCHAR_MAX + 256 + 2 - THRESHOLD   # 510
CODE_BIT = 16; NT = CODE_BIT + 3; TBIT = 5; CBIT = 9; PBIT = 4

class _Bits:
    def __init__(self, data):
        self.d = data; self.p = 0; self.bitbuf = 0; self.subbitbuf = 0; self.bitcount = 0
        self.fillbuf(16)
    def _byte(self):
        b = self.d[self.p] if self.p < len(self.d) else 0
        self.p += 1; return b
    def fillbuf(self, n):
        self.bitbuf = (self.bitbuf << n) & 0xffff
        while n > self.bitcount:
            n -= self.bitcount
            self.bitbuf |= (self.subbitbuf << n) & 0xffff
            self.subbitbuf = self._byte(); self.bitcount = 8
        self.bitcount -= n
        self.bitbuf |= (self.subbitbuf >> self.bitcount) & 0xffff
        self.subbitbuf &= (1 << self.bitcount) - 1
    def getbits(self, n):
        x = self.bitbuf >> (16 - n); self.fillbuf(n); return x

def _make_table(nchar, bitlen, tablebits):
    count = [0]*17; weight = [0]*17; start = [0]*18
    table = [0]*(1 << tablebits)
    avail = nchar; left = {}; right = {}
    for i in range(nchar): count[bitlen[i]] += 1
    start[1] = 0
    for i in range(1, 17): start[i+1] = (start[i] + (count[i] << (16 - i))) & 0xffff
    if start[17] != 0: raise ValueError('bad table')
    jutbits = 16 - tablebits
    for i in range(1, tablebits+1):
        start[i] >>= jutbits; weight[i] = 1 << (tablebits - i)
    for i in range(tablebits+1, 17): weight[i] = 1 << (16 - i)
    i = start[tablebits+1] >> jutbits
    if i != 0:
        k = 1 << tablebits
        while i != k: table[i] = 0; i += 1
    left = [0]*(2*nchar+2); right = [0]*(2*nchar+2)
    for ch in range(nchar):
        ln = bitlen[ch]
        if ln == 0: continue
        k = start[ln]; nxt = k + weight[ln]
        if ln <= tablebits:
            if nxt > (1 << tablebits): raise ValueError('bad table')
            for i in range(k, nxt): table[i] = ch
        else:
            p_is_table = True; idx = k >> 0
            i = ln - tablebits
            k &= 0xffff
            # walk tree
            j = k >> jutbits
            node = ('t', j)
            k = (k << tablebits) & 0xffff
            def getp(node): return table[node[1]] if node[0] == 't' else None
            cur = table[j]
            holder = ('t', j)
            while i != 0:
                if cur == 0:
                    right[avail] = left[avail] = 0
                    if holder[0] == 't': table[holder[1]] = avail
                    elif holder[0] == 'r': right[holder[1]] = avail
                    else: left[holder[1]] = avail
                    cur = avail; avail += 1
                if k & 0x8000: holder = ('r', cur); cur = right[cur]
                else: holder = ('l', cur); cur = left[cur]
                k = (k << 1) & 0xffff; i -= 1
            if holder[0] == 't': table[holder[1]] = ch
            elif holder[0] == 'r': right[holder[1]] = ch
            else: left[holder[1]] = ch
        start[ln] = nxt
    return table, left, right

def decode(data, size, dicbit=12):
    np_ = dicbit + 1
    b = _Bits(data)
    dicsiz = 1 << dicbit
    text = bytearray(dicsiz)
    pt_len = [0]*(max(NT, np_)+1); c_len = [0]*NC
    out = bytearray(); r = 0; blocksize = 0
    ct = pt = None
    def read_pt_len(nn, nbit, i_special):
        nonlocal pt
        n = b.getbits(nbit)
        for i in range(nn): pt_len[i] = 0
        if n == 0:
            c = b.getbits(nbit)
            for i in range(nn): pt_len[i] = 0
            pt = ([c]*256, [0]*4, [0]*4)
            return
        i = 0
        while i < n:
            c = b.bitbuf >> 13
            if c == 7:
                mask = 1 << 12
                while b.bitbuf & mask: mask >>= 1; c += 1
            b.fillbuf(3 if c < 7 else c - 3)
            pt_len[i] = c; i += 1
            if i == i_special:
                c = b.getbits(2)
                while c > 0 and i < nn: pt_len[i] = 0; i += 1; c -= 1
        while i < nn: pt_len[i] = 0; i += 1
        pt = _make_table(nn, pt_len, 8 if nn != NT else 8)
    def read_c_len():
        nonlocal ct
        n = b.getbits(CBIT)
        if n == 0:
            c = b.getbits(CBIT)
            for i in range(NC): c_len[i] = 0
            ct = ([c]*4096, [0]*4, [0]*4); return
        i = 0
        while i < n:
            tbl, l, rr = pt
            c = tbl[b.bitbuf >> 8]
            if c >= NT:
                mask = 1 << 7
                while True:
                    c = rr[c] if b.bitbuf & mask else l[c]
                    mask >>= 1
                    if c < NT: break
            b.fillbuf(pt_len[c])
            if c <= 2:
                if c == 0: c = 1
                elif c == 1: c = b.getbits(4) + 3
                else: c = b.getbits(CBIT) + 20
                while c > 0 and i < NC: c_len[i] = 0; i += 1; c -= 1
            else:
                c_len[i] = c - 2; i += 1
        while i < NC: c_len[i] = 0; i += 1
        ct = _make_table(NC, c_len, 12)
    def decode_c():
        nonlocal blocksize
        if blocksize == 0:
            blocksize = b.getbits(16)
            read_pt_len(NT, TBIT, 3)
            read_c_len()
            read_pt_len(np_, PBIT, -1)
        blocksize -= 1
        tbl, l, rr = ct
        j = tbl[b.bitbuf >> 4]
        if j >= NC:
            mask = 1 << 3
            while True:
                j = rr[j] if b.bitbuf & mask else l[j]
                mask >>= 1
                if j < NC: break
        b.fillbuf(c_len[j]); return j
    def decode_p():
        tbl, l, rr = pt
        j = tbl[b.bitbuf >> 8]
        if j >= np_:
            mask = 1 << 7
            while True:
                j = rr[j] if b.bitbuf & mask else l[j]
                mask >>= 1
                if j < np_: break
        b.fillbuf(pt_len[j])
        if j != 0:
            j = (1 << (j-1)) + b.getbits(j-1)
        return j
    while len(out) < size:
        c = decode_c()
        if c <= UCHAR_MAX:
            text[r] = c; out.append(c); r = (r+1) & (dicsiz-1)
        else:
            n = c - (UCHAR_MAX + 1 - THRESHOLD)
            i = (r - decode_p() - 1) & (dicsiz-1)
            for _ in range(n):
                c = text[i]; i = (i+1) & (dicsiz-1)
                text[r] = c; out.append(c); r = (r+1) & (dicsiz-1)
    return bytes(out[:size])
