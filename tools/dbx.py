"""Tiny DOSBox-X driver for verification: launch, send keys to the DOSBox window only, screenshot only that window.
Usage as module:  d = DBX(conf_path, exe_path); d.start(); d.key('enter'); d.shot('out.png'); d.stop()
"""
import ctypes, ctypes.wintypes as wt, subprocess, time, os, sys
from PIL import ImageGrab

user32 = ctypes.windll.user32
VK = {'enter': 0x0D, 'esc': 0x1B, 'space': 0x20, 'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27,
      'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f10': 0x79, 'tab': 0x09, 'n': 0x4E, 'y': 0x59}
WM_KEYDOWN, WM_KEYUP = 0x100, 0x101


def find_window(title_part):
    res = []
    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, l):
        if user32.IsWindowVisible(h):
            n = user32.GetWindowTextLengthW(h)
            buf = ctypes.create_unicode_buffer(n + 1); user32.GetWindowTextW(h, buf, n + 1)
            if title_part in buf.value: res.append(h)
        return True
    user32.EnumWindows(cb, 0)
    return res[0] if res else None


class DBX:
    def __init__(self, exe, conf, title='SC3TEST', limit=300):
        self.exe, self.conf, self.title, self.limit = exe, conf, title, limit
        self.p = None; self.h = None

    def start(self, wait=6):
        self.p = subprocess.Popen([self.exe, '-conf', self.conf, '-time-limit', str(self.limit), '-nogui', '-fastlaunch'],
                                  cwd=os.path.dirname(self.exe), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t = time.time()
        while time.time() - t < 30:
            self.h = find_window(self.title)
            if self.h: break
            time.sleep(0.5)
        time.sleep(wait)
        return self.h

    def key(self, name, hold=0.12):
        vk = VK[name] if name in VK else ord(name.upper())
        scan = user32.MapVirtualKeyW(vk, 0)
        user32.PostMessageW(self.h, WM_KEYDOWN, vk, 1 | (scan << 16))
        time.sleep(hold)
        user32.PostMessageW(self.h, WM_KEYUP, vk, 1 | (scan << 16) | (1 << 30) | (1 << 31))
        time.sleep(0.3)

    def shot(self, path):
        """Capture ONLY the DOSBox window contents (PrintWindow), never other screen content."""
        if not self.h or not user32.IsWindow(self.h): raise RuntimeError('DOSBox window not found')
        gdi32 = ctypes.windll.gdi32
        r = wt.RECT(); user32.GetWindowRect(self.h, ctypes.byref(r))
        w, h = r.right - r.left, r.bottom - r.top
        hdc = user32.GetDC(0); mdc = gdi32.CreateCompatibleDC(hdc); bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
        old = gdi32.SelectObject(mdc, bmp)
        user32.PrintWindow(self.h, mdc, 2)
        class BMI(ctypes.Structure):
            _fields_ = [('biSize', wt.DWORD), ('biWidth', wt.LONG), ('biHeight', wt.LONG), ('biPlanes', wt.WORD), ('biBitCount', wt.WORD),
                        ('biCompression', wt.DWORD), ('biSizeImage', wt.DWORD), ('x', wt.LONG), ('y', wt.LONG), ('c', wt.DWORD), ('i', wt.DWORD)]
        bi = BMI(ctypes.sizeof(BMI), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
        gdi32.SelectObject(mdc, old); gdi32.DeleteObject(bmp); gdi32.DeleteDC(mdc); user32.ReleaseDC(0, hdc)
        from PIL import Image
        Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1).convert('RGB').save(path)
        return path

    def click(self, x, y, right=False, hold=0.15):
        '''client-area coordinates of the DOSBox window'''
        lp = (y << 16) | (x & 0xffff)
        down, up, mk = (0x204, 0x205, 2) if right else (0x201, 0x202, 1)
        user32.PostMessageW(self.h, 0x200, 0, lp); time.sleep(0.15)
        user32.PostMessageW(self.h, down, mk, lp); time.sleep(hold)
        user32.PostMessageW(self.h, up, 0, lp); time.sleep(0.4)

    def stop(self):
        if self.p and self.p.poll() is None: self.p.terminate()
