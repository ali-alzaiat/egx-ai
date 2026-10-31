"""Turn out/raw.webm into the demo: trim to the tour, speed up long waits, burn the captions into
a strip below the app, then encode the MP4 and a GIF preview of the chart scene.

Usage: python post.py <path to ffmpeg> <out dir>
"""

import json
import subprocess
import sys
from pathlib import Path

FF, OUT = sys.argv[1], Path(sys.argv[2])
W, H, STRIP = 1280, 800, 80
FONT = "C\\:/Windows/Fonts/segoeui.ttf"
KEEP = 1.0  # seconds a long wait lasts after speed-up

tl = json.loads((OUT / "timeline.json").read_text(encoding="utf-8"))
start, end = tl["marks"]["start"], tl["marks"]["end"]

segs, t = [], start  # (from, to, speed) in recording time
for a, b in sorted(tl["waits"]):
    a, b = max(a, start), min(b, end)
    if b - a <= KEEP or a < t:
        continue
    segs.append((t, a, 1.0))
    segs.append((a, b, (b - a) / KEEP))
    t = b
segs.append((t, end, 1.0))


def mapped(x: float) -> float:
    """Recording time -> time in the finished video."""
    out = 0.0
    for a, b, k in segs:
        if x <= a:
            break
        out += (min(x, b) - a) / k
    return out


caps_dir = OUT / "caps"
caps_dir.mkdir(exist_ok=True)
draws = []
caps = [(mapped(at), text) for at, text in tl["caps"]]
total = mapped(end)
for i, (at, text) in enumerate(caps):
    until = caps[i + 1][0] if i + 1 < len(caps) else total
    if not text or until - at < 0.2:
        continue
    (caps_dir / f"{i:02d}.txt").write_text(text, encoding="utf-8")
    draws.append(
        f"drawtext=fontfile='{FONT}':textfile='caps/{i:02d}.txt':fontsize=27:fontcolor=white:"
        f"x=(w-text_w)/2:y={H}+({STRIP}-text_h)/2:enable='between(t,{at:.2f},{until:.2f})'"
    )

trims = [
    f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=(PTS-STARTPTS)/{k:.4f}[v{i}]" for i, (a, b, k) in enumerate(segs)
]
graph = (
    ";".join(trims) + ";" + "".join(f"[v{i}]" for i in range(len(segs)))
    + f"concat=n={len(segs)}:v=1:a=0,fps=30,pad={W}:{H + STRIP}:0:0:color=0x0b0f19,"
    + ",".join(draws) + "[out]"
)
(OUT / "graph.txt").write_text(graph, encoding="utf-8")
mp4 = OUT / "egx-ai-demo.mp4"
subprocess.run(
    [FF, "-v", "error", "-y", "-i", "raw.webm", "-/filter_complex", "graph.txt", "-map", "[out]",
     "-c:v", "libx264", "-preset", "slow", "-crf", "28", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
     mp4.name],
    check=True, cwd=OUT,
)

g0, g1 = mapped(tl["marks"]["gif_start"]), mapped(tl["marks"]["gif_end"])
vf = "fps=10,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer:bayer_scale=4"
subprocess.run(
    [FF, "-v", "error", "-y", "-ss", f"{g0:.2f}", "-t", f"{g1 - g0:.2f}", "-i", mp4.name, "-vf", vf, "egx-ai-demo.gif"],
    check=True, cwd=OUT,
)
print(f"video {total:.1f}s, gif {g1 - g0:.1f}s from {g0:.1f}s")
