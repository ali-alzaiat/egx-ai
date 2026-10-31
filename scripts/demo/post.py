"""Speed up the logged waits, encode the MP4 and a GIF preview of the chart scene."""

import json
import subprocess
import sys
from pathlib import Path

FF, OUT = sys.argv[1], Path(sys.argv[2])
tl = json.loads((OUT / "timeline.json").read_text(encoding="utf-8"))
end = tl["end"] + 1.0
KEEP = 2.0  # seconds a long wait lasts after speed-up

segs, t = [], 0.0  # (start, end, speed)
for a, b in sorted(tl["waits"]):
    if b - a <= KEEP:
        continue
    segs.append((t, a, 1.0))
    segs.append((a, b, (b - a) / KEEP))
    t = b
segs.append((t, end, 1.0))


def mapped(x: float) -> float:
    out = 0.0
    for a, b, k in segs:
        if x <= a:
            break
        out += (min(x, b) - a) / k
    return out


parts, labels = [], []
for i, (a, b, k) in enumerate(segs):
    parts.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=(PTS-STARTPTS)/{k:.4f}[v{i}]")
    labels.append(f"[v{i}]")
graph = ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(segs)}:v=1:a=0,fps=30[out]"
mp4 = OUT / "egx-ai-demo.mp4"
subprocess.run([FF, "-v", "error", "-y", "-i", str(OUT / "raw.webm"), "-filter_complex", graph, "-map", "[out]",
                "-c:v", "libx264", "-preset", "slow", "-crf", "28", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(mp4)], check=True)

g0, g1 = mapped(tl["marks"]["gif_start"]), mapped(tl["marks"]["gif_end"])
gif = OUT / "egx-ai-demo.gif"
vf = "fps=10,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer:bayer_scale=4"
subprocess.run([FF, "-v", "error", "-y", "-ss", f"{g0:.2f}", "-t", f"{g1 - g0:.2f}", "-i", str(mp4), "-vf", vf, str(gif)],
               check=True)
print(f"mp4 length {mapped(end):.1f}s, gif {g1 - g0:.1f}s from {g0:.1f}s")
