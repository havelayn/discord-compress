# Discord Compress

Shrinks videos so they fit under Discord's upload limit, without any setup. FFmpeg is bundled inside the exe.

## Download

Get `DiscordCompress.exe` from the [latest release](../../releases/latest). Windows only.

## Use

- **Drag** one or more videos onto `DiscordCompress.exe`, or
- **Double-click** it and pick videos in the file window.

Choose the target size (10 MB free, 50 MB Nitro Basic, 500 MB Nitro) and wait. The result is saved next to the original as `<name>_discord.mp4`.

## How it works

It works out the bitrate that fits the target size for the clip's length, then does a two-pass H.264 encode. Long clips are scaled down (1080p → 720p → 480p → 360p) and capped at 30 fps, because fewer pixels at a decent bitrate look better than blocky full HD.

## "Windows protected your PC"

The exe isn't code-signed, so SmartScreen may warn the first time. Click **More info → Run anyway**. If you'd rather not, run `discord_compress.py` with Python and FFmpeg on your PATH.

## Build it yourself

```
pip install pyinstaller
pyinstaller --onefile --console --name DiscordCompress --add-binary "path\to\ffmpeg.exe;." discord_compress.py
```

## License

GPL-3.0. The bundled `ffmpeg.exe` is an FFmpeg GPL build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/), with source at [ffmpeg.org](https://ffmpeg.org/download.html).
