"""Discord Compress: shrink videos so they fit under Discord's upload limit."""
import os
import re
import subprocess
import sys
import tempfile

AUDIO_KBPS = 96
SIZES = {"1": 10, "2": 50, "3": 500}  # Free, Nitro Basic, Nitro


def find_ffmpeg():
    # PyInstaller unpacks the bundled ffmpeg.exe next to the script in _MEIPASS
    bundled = os.path.join(getattr(sys, "_MEIPASS", ""), "ffmpeg.exe")
    return bundled if os.path.exists(bundled) else "ffmpeg"


FFMPEG = find_ffmpeg()


def get_duration(path):
    info = subprocess.run([FFMPEG, "-hide_banner", "-i", path],
                          capture_output=True, text=True, errors="replace").stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", info)
    if not m:
        return None
    h, mins, s = m.groups()
    return int(h) * 3600 + int(mins) * 60 + float(s)


def pick_files():
    import tkinter
    from tkinter import filedialog
    root = tkinter.Tk()
    root.withdraw()
    files = filedialog.askopenfilenames(
        title="Pick videos to compress for Discord",
        filetypes=[("Videos", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v"), ("All files", "*.*")])
    root.destroy()
    return list(files)


def ask_target():
    print("Target size:  1) 10 MB (free)   2) 50 MB (Nitro Basic)   3) 500 MB (Nitro)")
    choice = input("Pick 1-3 [Enter = 1]: ").strip()
    return SIZES.get(choice, 10)


def compress(path, target_mb):
    print(f"\n=== {os.path.basename(path)} ===")
    secs = get_duration(path)
    if not secs:
        print("Could not read this file, skipping.")
        return

    # 1 MB = 8000 kbit, keep 7% headroom for container overhead
    vkbps = int(target_mb * 8000 * 0.93 / secs) - AUDIO_KBPS
    if vkbps < 80:
        print(f"Too long for {target_mb} MB at watchable quality, skipping.")
        return

    # Lower the resolution (short side) when the bitrate is too thin for full HD
    if vkbps >= 2500:
        maxres = 1080
    elif vkbps >= 1200:
        maxres = 720
    elif vkbps >= 500:
        maxres = 480
    else:
        maxres = 360
    print(f"{secs:.0f}s long, video {vkbps} kbps, max {maxres}p")

    vopts = ["-c:v", "libx264", "-preset", "medium", "-b:v", f"{vkbps}k",
             "-vf", f"scale='trunc(iw*min(1,{maxres}/min(iw,ih))/2)*2':-2",
             "-pix_fmt", "yuv420p"]
    if vkbps < 2500:
        vopts += ["-fpsmax", "30"]

    passlog = os.path.join(tempfile.gettempdir(), "discordcompress")
    out = os.path.splitext(path)[0] + "_discord.mp4"
    base = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-stats", "-i", path]

    print("Pass 1/2...")
    subprocess.run(base + vopts + ["-pass", "1", "-passlogfile", passlog, "-an", "-f", "null", "NUL"])
    print("Pass 2/2...")
    result = subprocess.run(base + vopts + ["-pass", "2", "-passlogfile", passlog,
                                            "-c:a", "aac", "-b:a", f"{AUDIO_KBPS}k",
                                            "-movflags", "+faststart", out])
    for ext in ("-0.log", "-0.log.mbtree"):
        try:
            os.remove(passlog + ext)
        except OSError:
            pass

    if result.returncode == 0 and os.path.exists(out):
        print(f"Saved {os.path.basename(out)} ({os.path.getsize(out) / 1048576:.1f} MB)")
    else:
        print("Compression failed.")


def main():
    files = sys.argv[1:] or pick_files()
    if not files:
        print("No videos picked. Drag videos onto DiscordCompress.exe or pick them when it opens.")
    else:
        target = ask_target()
        for f in files:
            compress(f, target)
        print("\nAll done.")
    input("Press Enter to close.")


if __name__ == "__main__":
    main()
