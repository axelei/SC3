"""Patch SC3.EXE (DOS/4G LE executable): relocate translated strings into a new data object.

The original strings stay untouched; every fixup record that points at the start of a changed string is
re-targeted to a copy of the new text stored in an extra object (object 3) appended to the executable.
Nothing in ORIGINAL is modified: the patched image is built in memory and returned as bytes.
"""
import struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MZBASE = 217764
LEBASE = 228412
PAGE = 4096


def u32(d, o): return struct.unpack_from('<I', d, o)[0]


class Fixup:
    __slots__ = ('page', 'raw', 'st', 'fl', 'lst', 'srcs', 'tobj', 'toff', 'tobj_sz', 'toff_sz')


def parse_fixups(d, b, npages, fixpage, fixrec):
    pg = struct.unpack_from('<%dI' % (npages + 1), d, b + fixpage)
    recs = []
    for p in range(1, npages + 1):
        pos = b + fixrec + pg[p - 1]
        end = b + fixrec + pg[p]
        while pos < end:
            f = Fixup(); f.page = p; start = pos
            st, fl = d[pos], d[pos + 1]; pos += 2
            f.st, f.fl = st, fl; f.lst = bool(st & 0x20)
            if f.lst:
                cnt = d[pos]; pos += 1
            else:
                so = struct.unpack_from('<h', d, pos)[0]; pos += 2
            assert (fl & 3) == 0, 'only internal reference fixups supported'
            if fl & 0x40: f.tobj = struct.unpack_from('<H', d, pos)[0]; f.tobj_sz = 2
            else: f.tobj = d[pos]; f.tobj_sz = 1
            pos += f.tobj_sz
            if (st & 0xf) == 2:
                f.toff = None; f.toff_sz = 0
            elif fl & 0x10:
                f.toff = u32(d, pos); f.toff_sz = 4
            else:
                f.toff = struct.unpack_from('<H', d, pos)[0]; f.toff_sz = 2
            pos += f.toff_sz
            if f.lst:
                f.srcs = list(struct.unpack_from('<%dh' % cnt, d, pos)); pos += 2 * cnt
            else:
                f.srcs = [so]
            f.raw = d[start:pos]
            recs.append(f)
    return recs


def serialize_fixup(f):
    """Re-serialize a (possibly retargeted) fixup record."""
    fl = f.fl
    if f.toff is not None and f.toff > 0xffff: fl |= 0x10
    if f.tobj > 0xff: fl |= 0x40
    out = bytes([f.st, fl])
    if f.lst: out += bytes([len(f.srcs)])
    else: out += struct.pack('<h', f.srcs[0])
    out += struct.pack('<H', f.tobj) if (fl & 0x40) else bytes([f.tobj])
    if f.toff is not None:
        out += struct.pack('<I', f.toff) if (fl & 0x10) else struct.pack('<H', f.toff)
    if f.lst: out += struct.pack('<%dh' % len(f.srcs), *f.srcs)
    return out


def relocate_strings(exe, newstr, data_obj_index=2):
    """exe: bytes of SC3.EXE. newstr: {offset_in_data_object(int): bytes (no terminator)}.
    Returns patched exe bytes."""
    d = exe; b = LEBASE
    g = lambda o: u32(d, b + o)
    npages = g(0x14); pagesize = g(0x28); lastpage = g(0x2c)
    fixsz, ldrsz = g(0x30), g(0x38)
    objtab, objcnt, pagemap = g(0x40), g(0x44), g(0x48)
    restab, entry, fixpage, fixrec = g(0x58), g(0x5c), g(0x68), g(0x6c)
    impmod, datapages = g(0x70), g(0x80)
    assert pagesize == PAGE and objcnt == 2
    # sanity: layout assumptions
    assert pagemap == objtab + 24 * objcnt and restab == pagemap + 4 * npages
    assert fixrec == fixpage + 4 * (npages + 1)
    fixrec_len = impmod - fixrec
    recs = parse_fixups(d, b, npages, fixpage, fixrec)

    # --- build the new string object
    blob = bytearray(); newoff = {}
    for off in sorted(newstr):
        newoff[off] = len(blob); blob += newstr[off] + b'\0'
        while len(blob) % 4: blob.append(0)
    newpages = max(1, (len(blob) + PAGE - 1) // PAGE)
    obj2 = struct.unpack_from('<6I', d, b + objtab + 24)
    base3 = (obj2[1] + obj2[0] + 0xffff) & ~0xffff           # after obj2 virtual size, 64K aligned
    obj3 = struct.pack('<6I', len(blob), base3, obj2[2], npages + 1, newpages, 0)

    # --- retarget fixups
    changed = 0
    for f in recs:
        if f.tobj == data_obj_index and f.toff in newoff:
            f.tobj = 3; f.toff = newoff[f.toff]; f.raw = serialize_fixup(f); changed += 1
    # re-pack fixup records per page
    per_page = [[] for _ in range(npages)]
    for f in recs: per_page[f.page - 1].append(f.raw)
    fixrec_new = bytearray(); pg_off = []
    for p in range(npages):
        pg_off.append(len(fixrec_new)); fixrec_new += b''.join(per_page[p])
    pg_off.append(len(fixrec_new))
    pg_off += [len(fixrec_new)] * newpages
    fixpage_new = struct.pack('<%dI' % (npages + 1 + newpages), *pg_off)

    # --- page map
    pm_new = d[b + pagemap:b + pagemap + 4 * npages]
    for k in range(newpages):
        n = npages + 1 + k
        pm_new += bytes([(n >> 16) & 255, (n >> 8) & 255, n & 255, 0])

    objtab_new = d[b + objtab:b + objtab + 24 * objcnt] + obj3
    mid = d[b + restab:b + fixpage]                 # resident names + entry table (verbatim)
    tail_start = b + impmod                         # import tables .. up to data pages
    tail_end = MZBASE + datapages
    tail = d[tail_start:tail_end]

    # --- data pages: pad last page to full page, append new pages
    old_pages = d[tail_end:tail_end + (npages - 1) * PAGE + lastpage]
    old_pages += b'\0' * (npages * PAGE - len(old_pages))
    new_pages = bytes(blob) + b'\0' * (newpages * PAGE - len(blob))
    last_new = len(blob) - (newpages - 1) * PAGE

    # --- header
    h = bytearray(d[b:b + objtab])
    def put(o, v): struct.pack_into('<I', h, o, v)
    grow_obj = 24
    grow_pm = 4 * newpages
    grow_fp = 4 * newpages
    grow_rec = len(fixrec_new) - fixrec_len
    put(0x14, npages + newpages); put(0x2c, last_new)
    put(0x30, fixsz + grow_fp + grow_rec)
    put(0x38, ldrsz + grow_obj + grow_pm + grow_fp + grow_rec)
    put(0x44, objcnt + 1)
    put(0x48, pagemap + grow_obj)
    for o in (0x58, 0x5c): put(o, g(o) + grow_obj + grow_pm)
    put(0x68, fixpage + grow_obj + grow_pm); put(0x6c, fixrec + grow_obj + grow_pm + grow_fp)
    tot = grow_obj + grow_pm + grow_fp + grow_rec
    for o in (0x70, 0x78): put(o, g(o) + tot)
    put(0x80, datapages + tot)

    out = d[:b] + bytes(h) + objtab_new + pm_new + mid + fixpage_new + bytes(fixrec_new) + tail + old_pages + new_pages
    return out, changed, base3


if __name__ == '__main__':
    exe = open(sys.argv[1], 'rb').read()
    out, ch, base3 = relocate_strings(exe, {})
    print(len(exe), len(out), ch, hex(base3))
