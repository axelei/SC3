import sys,struct,re
sys.path.insert(0,'tools')
import leimg
from capstone import *
d,objs=leimg.load('ORIGINAL/SC3.EXE')
code=objs[0]['data'];data=objs[1]['data']
CB=0x10000;DB=0xa0000
md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=False;md.skipdata=True
def dis(addr,n=40,stop_ret=False):
    off=addr-CB
    cnt=0
    for i in md.disasm(code[off:off+n*8],addr):
        print('%x: %-24s %s %s'%(i.address,code[i.address-CB:i.address-CB+i.size].hex(),i.mnemonic,i.op_str))
        cnt+=1
        if cnt>=n: break
        if stop_ret and i.mnemonic.startswith('ret'): break
def xrefs(val):
    pat=struct.pack('<I',val)
    return [CB+m.start() for m in re.finditer(re.escape(pat),code)]
def strat(addr):
    off=addr-DB
    return data[off:off+80].split(b'\0')[0]
if __name__=='__main__':
    pass

def callers(target):
    res=[]
    for m in re.finditer(b'\xe8',code):
        p=m.start()
        if p+5>len(code): break
        rel=struct.unpack('<i',code[p+1:p+5])[0]
        if (CB+p+5+rel)&0xffffffff==target: res.append(CB+p)
    return res
def func_start(addr):
    # heuristic: scan back for typical padding then push
    return addr
