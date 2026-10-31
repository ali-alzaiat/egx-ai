import { Composition, staticFile, type CalculateMetadataFunction } from "remotion";
import { Demo, type DemoProps } from "./Demo";
import { makePlan, type Narration, type Timeline } from "./plan";

const FPS = 30;

const load = async <T,>(name: string): Promise<T> => {
  const res = await fetch(staticFile(name));
  if (!res.ok) throw new Error(`${name}: run narrate.py and record.py first`);
  return (await res.json()) as T;
};

// The plan is built from narrate.py and record.py's output in public/, so the length follows the recording.
const calculateMetadata: CalculateMetadataFunction<DemoProps> = async () => {
  const [timeline, narration] = await Promise.all([load<Timeline>("timeline.json"), load<Narration>("narration.json")]);
  const plan = makePlan(timeline, narration);
  return {
    durationInFrames: Math.ceil(plan.total * FPS),
    props: { plan, narration, page: timeline.size },
  };
};

export const Root = () => (
  <Composition
    id="Demo"
    component={Demo}
    width={1920}
    height={1080}
    fps={FPS}
    durationInFrames={1}
    defaultProps={{ plan: { hook: { outFrom: 0, outTo: 0 }, outro: { outFrom: 0, outTo: 0 }, pieces: [], beatStarts: {}, focus: [], total: 0 }, narration: {}, page: [1920, 1080] }}
    calculateMetadata={calculateMetadata}
  />
);
