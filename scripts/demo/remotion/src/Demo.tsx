import type { CSSProperties, ReactNode } from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Freeze,
  interpolate,
  OffthreadVideo,
  Sequence,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { type Camera, frame as frameBox, type Narration, type Plan, VOICE_DELAY } from "./plan";

export interface DemoProps {
  plan: Plan;
  narration: Narration;
  page: [number, number];
  [key: string]: unknown;
}

const FONT = '"Segoe UI", system-ui, sans-serif';
const BG = "linear-gradient(135deg, #0b1020 0%, #13203d 55%, #0d2a3a 100%)";
// The app window: 84% of the video width, centred, with room for captions below. The recorded page
// (3840x2160) is scaled down to fit it, so the camera can zoom about 2x before pixels show.
const WIN_W = 1920 * 0.84;
const WIN_X = (1920 - WIN_W) / 2;
const WIN_Y = 34;
const ZOOM_SECONDS = 0.9;

export const Demo = ({ plan, narration, page }: DemoProps) => {
  const { fps } = useVideoConfig();
  const f = (s: number) => Math.round(s * fps);
  const narrated = Object.entries(plan.beatStarts);
  return (
    <AbsoluteFill style={{ background: BG, fontFamily: FONT }}>
      <Sequence durationInFrames={f(plan.hook.outTo)}>
        <TitleCard />
      </Sequence>
      <Sequence from={f(plan.hook.outTo) - 1} durationInFrames={f(plan.outro.outFrom - plan.hook.outTo) + 1}>
        <Window plan={plan} page={page} />
      </Sequence>
      <Sequence from={f(plan.outro.outFrom)}>
        <EndCard />
      </Sequence>
      {narrated.map(([id, at]) => (
        <Sequence key={id} from={f(at + VOICE_DELAY)}>
          <Audio src={staticFile(`voice/${id}.mp3`)} />
        </Sequence>
      ))}
      <Captions plan={plan} narration={narration} />
    </AbsoluteFill>
  );
};

/** The recording in a framed window that slides in, with the camera zooming on each focus box. */
const Window = ({ plan, page }: { plan: Plan; page: [number, number] }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps + plan.hook.outTo;
  const enter = spring({ frame, fps, config: { damping: 200 }, durationInFrames: f2(0.8, fps) });
  const cam = cameraAt(plan, t, page);
  const [w, h] = page;
  const winScale = WIN_W / w;
  const pieces = plan.pieces.map((p, i) => {
    const from = Math.round((p.outFrom - plan.hook.outTo) * fps);
    const len = Math.max(1, Math.round((p.outTo - p.outFrom) * fps));
    const video =
      p.kind === "play" ? (
        <OffthreadVideo src={staticFile("rec/raw.mp4")} trimBefore={Math.round(p.recFrom * fps)} playbackRate={p.rate} muted style={FILL} />
      ) : (
        <Freeze frame={0}>
          <OffthreadVideo src={staticFile("rec/raw.mp4")} trimBefore={Math.round(p.rec * fps)} muted style={FILL} />
        </Freeze>
      );
    return (
      <Sequence key={i} from={from} durationInFrames={len} layout="none">
        {video}
      </Sequence>
    );
  });
  const style: CSSProperties = {
    position: "absolute",
    left: WIN_X,
    top: WIN_Y + interpolate(enter, [0, 1], [60, 0]),
    width: WIN_W,
    height: h * winScale,
    borderRadius: 14,
    overflow: "hidden",
    opacity: enter,
    boxShadow: "0 30px 80px rgba(0,0,0,.55), 0 0 0 1px rgba(255,255,255,.08)",
    background: "#fff",
  };
  return (
    <div style={style}>
      <div
        style={{
          position: "absolute",
          width: w,
          height: h,
          transformOrigin: "0 0",
          transform: `scale(${winScale * cam.scale}) translate(${w / 2 / cam.scale - cam.cx}px, ${h / 2 / cam.scale - cam.cy}px)`,
        }}
      >
        {pieces}
      </div>
    </div>
  );
};

const FILL: CSSProperties = { position: "absolute", inset: 0, width: "100%", height: "100%" };

const f2 = (s: number, fps: number) => Math.round(s * fps);

/** Eased move from the previous focus to the current one, ZOOM_SECONDS long. */
function cameraAt(plan: Plan, t: number, [w, h]: [number, number]): Camera {
  let prev: Camera = frameBox(null, w, h);
  let cur = prev;
  let since = Infinity;
  for (const ev of plan.focus) {
    if (ev.at > t) break;
    const next = frameBox(ev.box, w, h);
    // Where the camera was when this move began (mid-move if the last one had not finished).
    prev = blend(prev, cur, Math.min(1, since === Infinity ? 1 : (ev.at - since) / ZOOM_SECONDS));
    cur = next;
    since = ev.at;
  }
  const k = since === Infinity ? 1 : Math.min(1, (t - since) / ZOOM_SECONDS);
  return blend(prev, cur, Easing.bezier(0.45, 0, 0.2, 1)(k));
}

function blend(a: Camera, b: Camera, k: number): Camera {
  // Scale moves in log space so zooming in and out feel the same speed.
  const scale = Math.exp(Math.log(a.scale) + (Math.log(b.scale) - Math.log(a.scale)) * k);
  return { scale, cx: a.cx + (b.cx - a.cx) * k, cy: a.cy + (b.cy - a.cy) * k };
}

const Card = ({ children }: { children: ReactNode }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const k = spring({ frame, fps, config: { damping: 200 }, durationInFrames: f2(0.9, fps) });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", paddingBottom: 110 }}>
      <div style={{ textAlign: "center", color: "#fff", opacity: k, transform: `translateY(${interpolate(k, [0, 1], [24, 0])}px)` }}>
        {children}
      </div>
    </AbsoluteFill>
  );
};

const Logo = () => <div style={{ fontSize: 132, fontWeight: 700, letterSpacing: -3 }}>EGX AI</div>;

const TitleCard = () => (
  <Card>
    <Logo />
    <div style={{ fontSize: 40, marginTop: 10, opacity: 0.92 }}>Research for Egyptian Exchange stocks</div>
    <div style={{ fontSize: 26, marginTop: 28, opacity: 0.6, letterSpacing: 1 }}>Data · reasoning · checks · English and Arabic</div>
  </Card>
);

const EndCard = () => (
  <Card>
    <Logo />
    <div style={{ fontSize: 40, marginTop: 10, opacity: 0.92 }}>github.com/ali-alzaiat/egx-ai</div>
    <div style={{ fontSize: 26, marginTop: 28, opacity: 0.6 }}>Open source · a research aid, not investment advice</div>
  </Card>
);

/** The narration as captions below the window, one sentence at a time. */
const Captions = ({ plan, narration }: { plan: Plan; narration: Narration }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  let text = "";
  let k = 0;
  for (const [id, at] of Object.entries(plan.beatStarts)) {
    for (const s of narration[id]?.sentences ?? []) {
      const a = at + VOICE_DELAY + s.start;
      const b = at + VOICE_DELAY + s.end + 0.25;
      if (t >= a && t < b) {
        text = s.text;
        k = Math.min(1, (t - a) / 0.2, (b - t) / 0.2);
      }
    }
  }
  return (
    <div
      style={{
        position: "absolute",
        left: 120,
        right: 120,
        bottom: 34,
        textAlign: "center",
        color: "#fff",
        fontSize: 36,
        lineHeight: 1.3,
        opacity: k,
        textShadow: "0 2px 12px rgba(0,0,0,.6)",
      }}
    >
      {text}
    </div>
  );
};
