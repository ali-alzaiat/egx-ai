// The edit plan: how recording time maps to video time. Pure, no Remotion imports.

export type Box = [number, number, number, number];

export interface Timeline {
  size: [number, number];
  waitShown: number;
  beats: { id: string; start: number; end: number }[];
  waits: [number, number][];
  focus: [number, number[] | null][];
}

export interface Sentence {
  text: string;
  start: number;
  end: number;
}

export type Narration = Record<string, { seconds: number; sentences: Sentence[] }>;

/** A stretch of the video: the recording played (possibly sped up) or one recording frame held. */
export type Piece =
  | { kind: "play"; recFrom: number; recTo: number; rate: number; outFrom: number; outTo: number }
  | { kind: "hold"; rec: number; outFrom: number; outTo: number };

export interface Plan {
  hook: { outFrom: number; outTo: number };
  outro: { outFrom: number; outTo: number };
  pieces: Piece[];
  /** Where each narrated beat starts in the video. */
  beatStarts: Record<string, number>;
  focus: { at: number; box: Box | null }[];
  total: number;
}

export const VOICE_DELAY = 0.35; // seconds between a beat starting and its narration
const HOOK_TAIL = 0.9;
const OUTRO_TAIL = 2.2;
const BEAT_TAIL = 0.6;
// A beat whose actions outlast its narration by more than BEAT_SLACK plays its non-wait parts faster, up to MAX_SPEED.
const BEAT_SLACK = 2.5;
const MAX_SPEED = 1.7;

/** Play [from, to] of the recording at `speed`, speeding up every wait inside it to `shown` seconds. */
function playPieces(from: number, to: number, waits: [number, number][], shown: number, outFrom: number, speed = 1): Piece[] {
  const pieces: Piece[] = [];
  let t = from;
  let out = outFrom;
  const push = (a: number, b: number, rate: number): void => {
    if (b - a <= 1e-3) return;
    const len = (b - a) / rate;
    pieces.push({ kind: "play", recFrom: a, recTo: b, rate, outFrom: out, outTo: out + len });
    out += len;
  };
  for (const [wa, wb] of [...waits].sort((x, y) => x[0] - y[0])) {
    const a = Math.max(wa, t);
    const b = Math.min(wb, to);
    if (b - a <= shown) continue;
    push(t, a, speed);
    push(a, b, (b - a) / shown);
    t = b;
  }
  push(t, to, speed);
  return pieces;
}

export function makePlan(tl: Timeline, narration: Narration): Plan {
  const spoken = (id: string): number => narration[id]?.seconds ?? 0;
  const hookEnd = VOICE_DELAY + spoken("hook") + HOOK_TAIL;
  const pieces: Piece[] = [];
  const beatStarts: Record<string, number> = { hook: 0 };
  let out = hookEnd;
  for (const beat of tl.beats) {
    beatStarts[beat.id] = out;
    const need = beatStarts[beat.id] + VOICE_DELAY + spoken(beat.id) + BEAT_TAIL;
    let played = playPieces(beat.start, beat.end, tl.waits, tl.waitShown, out);
    const length = played.length ? played[played.length - 1].outTo - out : 0;
    const speed = Math.min(MAX_SPEED, Math.max(1, length / (need - out + BEAT_SLACK)));
    if (speed > 1) played = playPieces(beat.start, beat.end, tl.waits, tl.waitShown, out, speed);
    pieces.push(...played);
    out = played.length ? played[played.length - 1].outTo : out;
    if (out < need) {
      pieces.push({ kind: "hold", rec: beat.end - 0.05, outFrom: out, outTo: need });
      out = need;
    }
  }
  beatStarts.outro = out;
  const outroEnd = out + VOICE_DELAY + spoken("outro") + OUTRO_TAIL;
  const focus = tl.focus.map(([at, box]) => ({ at: recToOut(pieces, at), box: box ? (box as Box) : null }));
  return { hook: { outFrom: 0, outTo: hookEnd }, outro: { outFrom: out, outTo: outroEnd }, pieces, beatStarts, focus, total: outroEnd };
}

/** Recording time -> video time (times before or after the recorded part clamp to its ends). */
export function recToOut(pieces: Piece[], rec: number): number {
  for (const p of pieces) {
    if (p.kind === "play" && rec <= p.recTo) {
      return rec <= p.recFrom ? p.outFrom : p.outFrom + (rec - p.recFrom) / p.rate;
    }
  }
  return pieces.length ? pieces[pieces.length - 1].outTo : 0;
}

export interface Camera {
  scale: number;
  cx: number;
  cy: number;
}

/** The camera that frames `box` on a w x h page: as close as fits, at most `maxScale`, never past the edges. */
export function frame(box: Box | null, w: number, h: number, maxScale = 1.9): Camera {
  if (!box) return { scale: 1, cx: w / 2, cy: h / 2 };
  const [x, y, bw, bh] = box;
  const scale = Math.min(maxScale, Math.max(1, Math.min(w / bw, h / bh)));
  const halfW = w / 2 / scale;
  const halfH = h / 2 / scale;
  const clamp = (v: number, lo: number, hi: number): number => Math.min(hi, Math.max(lo, v));
  return { scale, cx: clamp(x + bw / 2, halfW, w - halfW), cy: clamp(y + bh / 2, halfH, h - halfH) };
}
