"""Discord Compress: shrink videos so they fit under Discord's upload limit."""
import json
import os
import re
import subprocess
import sys
import tempfile
import threading

import webview
from webview.dom import DOMEventHandler

AUDIO_KBPS = 96
HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def find_ffmpeg():
    # PyInstaller unpacks the bundled ffmpeg.exe into _MEIPASS
    bundled = os.path.join(HERE, "ffmpeg.exe")
    return bundled if os.path.exists(bundled) else "ffmpeg"


FFMPEG = find_ffmpeg()


def run(cmd, **kw):
    return subprocess.run(cmd, stdin=subprocess.DEVNULL, creationflags=NO_WINDOW, **kw)


def get_duration(path):
    info = run([FFMPEG, "-hide_banner", "-i", path],
               capture_output=True, text=True, errors="replace").stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", info)
    if not m:
        return None
    h, mins, s = m.groups()
    return int(h) * 3600 + int(mins) * 60 + float(s)


def file_info(path):
    return {"path": path, "name": os.path.basename(path),
            "size_mb": os.path.getsize(path) / 1048576, "duration": get_duration(path)}


def encode_pass(cmd, secs, on_pct):
    # -progress writes key=value lines; out_time_us tells how far the pass is
    proc = subprocess.Popen(cmd + ["-progress", "pipe:1", "-nostats"], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                            creationflags=NO_WINDOW)
    for line in proc.stdout:
        if line.startswith("out_time_us="):
            try:
                on_pct(min(1.0, int(line[12:]) / 1e6 / secs))
            except ValueError:
                pass
    return proc.wait()


def compress(path, target_mb, report):
    """Two-pass encode of path to fit target_mb. report(pct, status) is called as it goes."""
    secs = get_duration(path)
    if not secs:
        return False, "Can't read this file", None

    # 1 MB = 8000 kbit, keep 7% headroom for container overhead
    vkbps = int(target_mb * 8000 * 0.93 / secs) - AUDIO_KBPS
    if vkbps < 80:
        return False, f"Too long for {target_mb} MB", None

    # Lower the resolution (short side) when the bitrate is too thin for full HD
    if vkbps >= 2500:
        maxres = 1080
    elif vkbps >= 1200:
        maxres = 720
    elif vkbps >= 500:
        maxres = 480
    else:
        maxres = 360

    vopts = ["-c:v", "libx264", "-preset", "medium", "-b:v", f"{vkbps}k",
             "-vf", f"scale='trunc(iw*min(1,{maxres}/min(iw,ih))/2)*2':-2",
             "-pix_fmt", "yuv420p"]
    if vkbps < 2500:
        vopts += ["-fpsmax", "30"]

    passlog = os.path.join(tempfile.gettempdir(), "discordcompress")
    out = os.path.splitext(path)[0] + "_discord.mp4"
    base = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", path]

    encode_pass(base + vopts + ["-pass", "1", "-passlogfile", passlog, "-an", "-f", "null", "NUL"],
                secs, lambda t: report(t * 50, f"Analyzing · {maxres}p"))
    code = encode_pass(base + vopts + ["-pass", "2", "-passlogfile", passlog,
                                       "-c:a", "aac", "-b:a", f"{AUDIO_KBPS}k",
                                       "-movflags", "+faststart", out],
                       secs, lambda t: report(50 + t * 50, f"Encoding · {maxres}p"))
    for ext in ("-0.log", "-0.log.mbtree"):
        try:
            os.remove(passlog + ext)
        except OSError:
            pass

    if code == 0 and os.path.exists(out):
        return True, "Done", out
    return False, "Compression failed", None


class Api:
    def __init__(self):
        self._window = None
        self.busy = False

    def _js(self, fn, arg=None):
        self._window.evaluate_js(f"{fn}({json.dumps(arg) if arg is not None else ''})")

    def add_paths(self, paths):
        infos = [file_info(p) for p in paths if p and os.path.isfile(p)]
        if infos:
            self._js("addFiles", infos)

    def pick_files(self):
        picked = self._window.create_file_dialog(
            webview.FileDialog.OPEN, allow_multiple=True,
            file_types=("Videos (*.mp4;*.mov;*.mkv;*.avi;*.webm;*.m4v)", "All files (*.*)"))
        return [file_info(p) for p in picked or []]

    def start(self, paths, target_mb):
        if self.busy:
            return
        self.busy = True
        threading.Thread(target=self._work, args=(paths, target_mb), daemon=True).start()

    def _work(self, paths, target_mb):
        for path in paths:
            last = [-1]

            def report(pct, status, path=path, last=last):
                if int(pct) != last[0]:  # throttle to whole percents
                    last[0] = int(pct)
                    self._js("onProgress", {"path": path, "pct": pct, "status": status, "done": False})

            ok, status, out = compress(path, target_mb, report)
            self._js("onProgress", {"path": path, "pct": 100 if ok else 0, "status": status,
                                    "done": True, "ok": ok, "out": out,
                                    "out_mb": os.path.getsize(out) / 1048576 if ok else 0})
        self.busy = False
        self._js("onAllDone")

    def reveal(self, path):
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])

    def minimize(self):
        self._window.minimize()

    def close(self):
        self._window.destroy()


def round_corners(window):
    # Frameless windows are square on Windows 11 unless DWM is asked for rounded corners
    try:
        import ctypes
        hwnd = window.native.Handle.ToInt32()
        pref = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
    except Exception:
        pass


def main():
    api = Api()
    window = webview.create_window(
        "Discord Compress", os.path.join(HERE, "ui", "index.html"), js_api=api,
        width=460, height=640, resizable=False, frameless=True, easy_drag=False,
        background_color="#07070D")
    api._window = window

    def on_drop(e):
        api.add_paths([f.get("pywebviewFullPath") for f in e["dataTransfer"].get("files", [])])

    def on_loaded():
        window.dom.document.events.dragover += DOMEventHandler(lambda e: None, True, True)
        window.dom.document.events.drop += DOMEventHandler(on_drop, True, True)
        # videos dragged onto the exe icon arrive as arguments
        api.add_paths(sys.argv[1:])

    window.events.shown += lambda: round_corners(window)
    window.events.loaded += on_loaded
    webview.start(icon=os.path.join(HERE, "icon.ico"))


if __name__ == "__main__":
    main()
