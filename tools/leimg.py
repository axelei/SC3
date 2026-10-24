"""Build flat memory image of the LE program inside SC3.EXE (read-only use of ORIGINAL)."""
import struct
def load(path, mzbase=217764, lebase=228412):
    d = open(path, 'rb').read()
    b = lebase
    (npages,) = struct.unpack('<I', d[b+0x14:b+0x18])
    objtab, objcnt, pagemap = struct.unpack('<III', d[b+0x40:b+0x4c])
    pagesize, lastpage = struct.unpack('<II', d[b+0x28:b+0x30])
    datapages, = struct.unpack('<I', d[b+0x80:b+0x84])
    objs = []
    for i in range(objcnt):
        vs, base, fl, pmi, pc, _ = struct.unpack('<6I', d[b+objtab+24*i:b+objtab+24*i+24])
        objs.append(dict(size=vs, base=base, flags=fl, pmi=pmi, pc=pc))
    pages = []
    for i in range(npages):
        e = d[b+pagemap+4*i:b+pagemap+4*i+4]
        pages.append(e)
    def page(i):  # i 1-based
        off = mzbase + datapages + (i-1)*pagesize
        ln = pagesize if i < npages else lastpage
        return d[off:off+ln].ljust(pagesize, b'\0')
    mem = {}
    for o in objs:
        buf = bytearray()
        for k in range(o['pc']):
            buf += page(o['pmi']+k)
        o['data'] = bytes(buf[:max(o['size'], len(buf))])
    return d, objs
if __name__ == '__main__':
    d, objs = load('ORIGINAL/SC3.EXE')
    for o in objs: print({k: (hex(v) if isinstance(v, int) else len(v)) for k, v in o.items()})
