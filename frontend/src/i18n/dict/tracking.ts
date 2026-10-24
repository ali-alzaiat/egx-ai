import type { CopyEntry } from "./types";

/** Watchlists, alerts and events. Owned by the Tracking page lane; empty until that lane lands. */
export const TRACKING_COPY = {} as const satisfies Record<string, CopyEntry>;
