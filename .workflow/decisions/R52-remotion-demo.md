# R52 Demo video rebuilt with Remotion

Owner request (2026-10-31): "create a demo using remotion", after asking how the demo could be better.

| # | Decision | Owner's choice |
|---|---|---|
| D1 | What the video shows | **One-stock story, ~90 s**: one question about COMI from the dashboard to the assistant, a hook in the first seconds. |
| D2 | Voice-over | **Voice + captions**: English narration from edge-tts (Microsoft neural voices; the script text goes to Microsoft's speech service), captions too since README previews play muted. |
| D3 | Arabic | **Single video, voice always English**: the story ends with the UI switched to Arabic (RTL) and an Arabic question to the assistant; the narration stays English. |
| D4 | Where it lives | **`scripts/demo/remotion`** with its own `package.json` (Remotion pinned to 4.0.534); the app's frontend dependencies are untouched. Rendered MP4/GIF go to `docs/media`. |

Pipeline: `narrate.py` (script in `story.json` → per-beat MP3 + sentence timings) → `record.py` (Playwright
at 3840x2160 with the page at CSS zoom 2, so it lays out as 1080p but the camera can zoom 2x sharply; draws a
cursor and click ripples in the page; logs beats, zoom targets and loading waits) → Remotion composition in
`scripts/demo/remotion` (title card, the recording in a window, waits sped up to 1 s, long beats played up to
1.7x, eased camera zooms, captions, narration per beat, end card) → `npx remotion render`.
The tour still never shows statement amounts (vendor data).
