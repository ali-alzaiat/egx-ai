"""Speak each beat of story.json with edge-tts (Microsoft neural voices; the text goes to Microsoft's
speech service). Writes remotion/public/voice/<beat>.mp3 and remotion/public/narration.json with each
beat's spoken length and sentence timings (for captions).

Usage: python narrate.py
"""

import asyncio
import json
from pathlib import Path

import edge_tts

HERE = Path(__file__).parent
PUBLIC = HERE / "remotion" / "public"
TICK = 10_000_000  # edge-tts offsets are in 100 ns units


async def speak(text: str, voice: str, rate: str, mp3: Path) -> dict[str, object]:
    sentences: list[dict[str, object]] = []
    with mp3.open("wb") as f:
        async for chunk in edge_tts.Communicate(text, voice, rate=rate).stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "SentenceBoundary":
                start = chunk["offset"] / TICK
                sentences.append({"text": chunk["text"], "start": start, "end": start + chunk["duration"] / TICK})
    if not sentences:
        raise RuntimeError(f"no sentence timings for {mp3.name}")
    return {"seconds": sentences[-1]["end"], "sentences": sentences}


async def main() -> None:
    story = json.loads((HERE / "story.json").read_text(encoding="utf-8"))
    (PUBLIC / "voice").mkdir(parents=True, exist_ok=True)
    out = {}
    for beat in story["beats"]:
        out[beat["id"]] = await speak(beat["say"], story["voice"], story["rate"], PUBLIC / "voice" / f"{beat['id']}.mp3")
        print(f"{beat['id']}: {out[beat['id']]['seconds']:.1f}s")
    (PUBLIC / "narration.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
