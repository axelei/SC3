"""Parse LE fixup records of SC3.EXE -> list of (obj_index(0-based), page_offset_abs, srctype, target_obj, target_off)."""
import struct, sys
sys.path.insert(0, 'tools')

def parse(path='ORIGINAL/SC3.EXE', lebase=228412):
    d = open(path, 'rb').read(); b = lebase
    g = lambda o: struct.unpack('<I', d[b+o:b+o+4])[0]
    npages = g(0x14); pagesize = g(0x28)
    fixpage = g(0x68); fixrec = g(0x6c)
    pg = struct.unpack('<%dI' % (npages+1), d[b+fixpage:b+fixpage+4*(npages+1)])
    objtab = g(0x40); objcnt = g(0x44)
    objs = []
    for i in range(objcnt):
        vs, base, fl, pmi, pc, _ = struct.unpack('<6I', d[b+objtab+24*i:b+objtab+24*i+24]); objs.append((pmi, pc))
    def obj_of_page(p):  # 1-based page
        for oi, (pmi, pc) in enumerate(objs):
            if pmi <= p < pmi+pc: return oi, p-pmi
    out = []
    for p in range(1, npages+1):
        s, e = pg[p-1], pg[p]
        pos = b + fixrec + s; end = b + fixrec + e
        oi, pidx = obj_of_page(p)
        while pos < end:
            st, fl = d[pos], d[pos+1]; pos += 2
            lst = st & 0x20
            if lst:
                cnt = d[pos]; pos += 1
            else:
                so = struct.unpack('<h', d[pos:pos+2])[0]; pos += 2
            ftype = fl & 3
            if ftype == 0:
                if fl & 0x40: tobj = struct.unpack('<H', d[pos:pos+2])[0]; pos += 2
                else: tobj = d[pos]; pos += 1
                stype = st & 0xf
                if stype == 2:   # 16-bit selector
                    toff = None
                elif fl & 0x10:
                    toff = struct.unpack('<I', d[pos:pos+4])[0]; pos += 4
                else:
                    toff = struct.unpack('<H', d[pos:pos+2])[0]; pos += 2
                if lst:
                    offs = struct.unpack('<%dh' % cnt, d[pos:pos+2*cnt]); pos += 2*cnt
                else: offs = [so]
                for so_ in offs:
                    out.append((oi, pidx*pagesize + so_, st & 0xf, tobj-1, toff))
            else:
                raise NotImplementedError('fixup type %d' % ftype)
    return out

if __name__ == '__main__':
    f = parse(); print(len(f))
    import collections
    print(collections.Counter((o, s, t) for o, _, s, t, _ in f))
