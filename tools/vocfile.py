"""STAR001.VOC voice archive.
u16 count, u32 offsets[count] (0 = unused slot, entries 4096-aligned).
Entry: u16 type, u32 payload_size, 44-byte RIFF/WAVE header, payload.
  type 0    : payload is raw PCM (size = RIFF data size)
  type 0x20 : payload is block-ADPCM (tools/sc3voc.py), type value = samples per delta block"""
import struct, sys, wave, io
sys.path.insert(0, 'tools')
import sc3voc

ALIGN = 4096

class Archive:
    def __init__(self, path):
        self.path = path
        self.f = open(path, 'rb')
        self.n = struct.unpack('<H', self.f.read(2))[0]
        self.offs = list(struct.unpack('<%dI' % self.n, self.f.read(4*self.n)))
        self.f.seek(0, 2); self.size = self.f.tell()
        nz = sorted(o for o in self.offs if o)
        self.ends = {o: (nz[k+1] if k+1 < len(nz) else self.size) for k, o in enumerate(nz)}
    def slots(self): return [i for i, o in enumerate(self.offs) if o]
    def raw(self, slot):
        o = self.offs[slot]; self.f.seek(o); h = self.f.read(50)
        typ, ln = struct.unpack('<HI', h[:6])
        return typ, h[6:50], self.f.read(ln)
    def raw_entry_bytes(self, slot):
        typ, hdr, payload = self.raw(slot)
        return struct.pack('<HI', typ, len(payload)) + hdr + payload
    def wav(self, slot):
        typ, hdr, payload = self.raw(slot)
        if typ == 0: return hdr + payload
        dl = struct.unpack('<I', hdr[40:44])[0]
        pcm = sc3voc.decode(payload, typ)
        assert len(pcm) == dl, (slot, len(pcm), dl)
        return hdr + pcm

def wav_to_entry(wavbytes):
    """Convert a WAV file (PCM, any rate, mono 8/16-bit) to a raw (type 0) archive entry."""
    w = wave.open(io.BytesIO(wavbytes), 'rb')
    ch, sw, rate, nf = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    pcm = w.readframes(nf)
    bits = sw*8; align = ch*sw
    hdr = (b'RIFF' + struct.pack('<I', 36 + len(pcm)) + b'WAVEfmt ' + struct.pack('<IHHIIHH', 16, 1, ch, rate, rate*align, align, bits)
           + b'data' + struct.pack('<I', len(pcm)))
    assert len(hdr) == 44
    return struct.pack('<HI', 0, len(pcm)) + hdr + pcm

def build(entries, count=3879):
    """entries: dict slot -> entry bytes. Returns archive bytes."""
    head = 2 + 4*count
    pos = (head + ALIGN - 1) // ALIGN * ALIGN
    offs = [0]*count; body = bytearray()
    for slot in sorted(entries):
        e = entries[slot]; offs[slot] = pos + len(body)
        body += e; pad = (-len(body)) % ALIGN; body += b'\0'*pad
    out = bytearray(struct.pack('<H', count) + struct.pack('<%dI' % count, *offs))
    out += b'\0' * (pos - len(out))
    return bytes(out + body)
