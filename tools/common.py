import os, sys, json, hashlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIG = os.path.join(ROOT, 'ORIGINAL')      # read-only source of truth
ASSETS = os.path.join(ROOT, 'ASSETS')
SC3E = os.path.join(ROOT, 'SC3E')
sys.path.insert(0, os.path.join(ROOT, 'tools'))

def orig(name): return os.path.join(ORIG, name)
def assets(*p): return os.path.join(ASSETS, *p)
def sc3e(name): return os.path.join(SC3E, name)
def ensure(path):
    os.makedirs(os.path.dirname(path) if os.path.splitext(path)[1] else path, exist_ok=True)
def sha1(b): return hashlib.sha1(b).hexdigest()
def sha1_file(p):
    h = hashlib.sha1()
    with open(p, 'rb') as f:
        for ch in iter(lambda: f.read(1 << 20), b''): h.update(ch)
    return h.hexdigest()

def load_manifest():
    p = assets('manifest.json')
    return json.load(open(p)) if os.path.exists(p) else {}
def save_manifest(m):
    ensure(assets('manifest.json'))
    json.dump(m, open(assets('manifest.json'), 'w'), indent=0, sort_keys=True)
