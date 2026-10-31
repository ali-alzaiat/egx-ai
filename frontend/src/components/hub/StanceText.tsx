import { useLang } from "../../i18n/useLang";
import type { LimitationEntry, ReasonEntry } from "../../lib/stanceModel";
import { limitationText, reasonText } from "../../lib/stanceText";
import { BackendText } from "../ui/BackendText";

/** A stance reason in the page language; the API's English text when its codes are missing or unknown (R51). */
export function ReasonLine({ entry }: { entry: ReasonEntry }) {
  const { t, locale } = useLang();
  const text = reasonText(entry.parts, { t, locale });
  return text !== null ? <>{text}</> : <BackendText>{entry.text}</BackendText>;
}

/** A stance limitation in the page language; the API's English text when its code is missing or unknown (R51). */
export function LimitationLine({ entry }: { entry: LimitationEntry }) {
  const { t, locale } = useLang();
  const text = limitationText(entry.item, { t, locale });
  return text !== null ? <>{text}</> : <BackendText>{entry.text}</BackendText>;
}
