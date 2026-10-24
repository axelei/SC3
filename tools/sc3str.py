"""SC3STR.DAT codec (Star Control 3 string table).

Layout
  u16 version(=1), u16 count, u32 total_len (= sum of sizes = length of bit data)
  u16 sizes[count]            compressed byte length of each string
  i16 hdr                     = 510 (unused here; kept verbatim)
  i16 tree[511]               Huffman node pairs, root at index 508 of tree[] (tree = file i16 array after hdr)
  u16 word_offs[257]; words   256 NUL-terminated dictionary words
  bit data: each string byte-aligned, bits LSB first, Huffman symbols:
      sym 1      -> end of string
      sym 27     -> next symbol t is dictionary word index t-1
      other sym  -> byte sym-1
"""
import struct, heapq, collections

ESC, EOS = 27, 1

def parse(path):
    d = open(path, 'rb').read()
    ver, n, total = struct.unpack('<HHI', d[:8])
    sizes = struct.unpack('<%dH' % n, d[8:8+2*n])
    o = 8 + 2*n
    v = struct.unpack('<512h', d[o:o+1024]); o += 1024
    offs = struct.unpack('<257H', d[o:o+514]); o += 514
    words = [d[o+offs[i]:o+offs[i+1]].rstrip(b'\0') for i in range(256)]
    o += offs[256]
    return dict(ver=ver, n=n, total=total, sizes=sizes, tree=list(v[1:])+[0], words=words, data=d[o:], hdr=v[0])

def decode_string(seg, tree, words, root=508, expand=True):
    out = bytearray(); pos = 0; nbits = len(seg)*8; pend = False
    while pos < nbits:
        nd = root
        while True:
            if pos >= nbits: return bytes(out)
            c = tree[nd + ((seg[pos >> 3] >> (pos & 7)) & 1)]; pos += 1
            if c <= 0: break
            nd = c
        s = -c
        if pend:
            out += words[s-1] if expand else b'\x1b%c' % (s-1) ; pend = False
        elif s == EOS: return bytes(out)
        elif s == ESC: pend = True
        else: out.append(s-1)
    return bytes(out)

def decode_all(path):
    p = parse(path); off = 0; res = []
    for sz in p['sizes']:
        res.append(decode_string(p['data'][off:off+sz], p['tree'], p['words'])); off += sz
    return res

def build_tree(freq):
    """Huffman tree in the file's node-pair layout. freq: {sym:count}. Returns (tree[511], root)."""
    # tree entries: leaf -> -sym ; node -> index of pair (even). Root must be reachable at returned index.
    syms = sorted(freq)
    heap = [(freq[s], i, ('L', s)) for i, s in enumerate(syms)]
    heapq.heapify(heap); cnt = len(heap)
    nodes = []  # list of (left,right) as ('L',s) or ('N',k)
    while len(heap) > 1:
        a = heapq.heappop(heap); b = heapq.heappop(heap)
        nodes.append((a[2], b[2])); heapq.heappush(heap, (a[0]+b[0], cnt, ('N', len(nodes)-1))); cnt += 1
    T = [0]*512
    def enc(x): return -x[1] if x[0] == 'L' else 2*x[1]
    for k, (l, r) in enumerate(nodes):
        T[2*k] = enc(l); T[2*k+1] = enc(r)
    return T, 2*(len(nodes)-1)


def _encode_file(strings, words):
    """strings: list[bytes] (no terminator). Returns bytes of a complete SC3STR.DAT using a fresh Huffman tree
    over all 256 byte values (leaf = -(byte+1)), terminator byte 0, no dictionary-word escapes."""
    import struct
    freq = collections.Counter({b: 1 for b in range(256)})
    for s in strings:
        for b in s: freq[b] += 1
        freq[0] += 1
    # Huffman over 256 leaves -> 255 internal nodes -> 510 entries, root = last node (index 508)
    heap = [(f, i, ('L', b)) for i, (b, f) in enumerate(sorted(freq.items()))]
    heapq.heapify(heap); uid = len(heap); nodes = []
    while len(heap) > 1:
        a = heapq.heappop(heap); b = heapq.heappop(heap)
        nodes.append((a[2], b[2])); heapq.heappush(heap, (a[0]+b[0], uid, ('N', len(nodes)-1))); uid += 1
    T = [0]*510
    enc = lambda x: -(x[1]+1) if x[0] == 'L' else 2*x[1]
    for k, (l, r) in enumerate(nodes): T[2*k] = enc(l); T[2*k+1] = enc(r)
    root = 2*(len(nodes)-1); assert root == 508
    # code table: path bits (LSB first on read)
    codes = {}
    def walk(nd, bits):
        for bit in (0, 1):
            c = T[nd+bit]
            if c < 0: codes[-c-1] = bits + [bit]
            else: walk(c, bits + [bit])
    import sys; sys.setrecursionlimit(5000)
    walk(root, [])
    blobs = []
    for s in strings:
        bits = []
        for b in s + b'\0': bits += codes[b]
        out = bytearray((len(bits)+7)//8)
        for i, bt in enumerate(bits):
            if bt: out[i >> 3] |= 1 << (i & 7)
        blobs.append(bytes(out))
    n = len(strings); assert all(len(x) < 65536 for x in blobs)
    total = sum(len(x) for x in blobs)
    wdata = b''.join(w + b'\0' for w in words); offs = []; p = 0
    for w in words: offs.append(p); p += len(w) + 1
    hdr = struct.pack('<HHI', 1, n, total) + struct.pack('<%dH' % n, *[len(x) for x in blobs])
    hdr += struct.pack('<H', 510) + struct.pack('<510h', *T)
    hdr += struct.pack('<H', 256) + struct.pack('<256H', *offs) + struct.pack('<H', len(wdata)) + wdata
    return hdr + b''.join(blobs)

def build(strings, orig_path='ORIGINAL/SC3STR.DAT'):
    p = parse(orig_path)
    return _encode_file(strings, p['words'])
