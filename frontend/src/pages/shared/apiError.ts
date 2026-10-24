import type { CopyKey, CopyParams } from "../../i18n";

type Translate = (key: CopyKey, params?: CopyParams) => string;

export interface ErrorView {
  /** Localized sentence for the reader. */
  text: string;
  /** Backend-supplied detail (English, not localized yet), shown in a `lang="en"` span. */
  detail: string | null;
}

/** HTTP status from the client's "API error: 422" messages; null for anything else. */
export function statusOf(err: unknown): number | null {
  if (!(err instanceof Error)) return null;
  const match = /^API error: (\d{3})$/.exec(err.message);
  return match?.[1] ? Number(match[1]) : null;
}

const STATUS_KEYS: ReadonlyArray<readonly [(s: number) => boolean, CopyKey]> = [
  [(s) => s === 401 || s === 403, "err_auth"],
  [(s) => s === 404, "err_not_found"],
  [(s) => s === 409, "err_conflict"],
  [(s) => s === 413, "err_too_large"],
  [(s) => s === 422, "err_rejected"],
  [(s) => s >= 500, "err_server"],
];

/**
 * Turn a thrown request error into a localized sentence. The shared client
 * throws "API error: <status>"; the manual-filing call throws the server's
 * 422 detail instead, which is kept as `detail` (never shown as the headline).
 */
export function describeError(err: unknown, t: Translate, fallback: CopyKey): ErrorView {
  const status = statusOf(err);
  if (status !== null) {
    const hit = STATUS_KEYS.find(([test]) => test(status));
    return { text: t(hit ? hit[1] : fallback), detail: null };
  }
  if (err instanceof Error && err.message.trim() !== "") {
    return { text: t(fallback), detail: err.message };
  }
  return { text: t(fallback), detail: null };
}
