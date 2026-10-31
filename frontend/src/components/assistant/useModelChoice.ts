import { useCallback, useState } from "react";
import { readStored, writeStored } from "../../lib/storage";

export const MODEL_STORAGE_KEY = "egx-assistant-model";

/**
 * The model sent with chat requests. `pick` is the user's choice and is remembered across visits; `resolve` is the
 * model the server list settled on (saved choice unavailable, so default or first) and is not remembered, so changing
 * the default model in Admin later still takes effect.
 */
export function useModelChoice(): { modelChoice: string | null; pick: (id: string) => void; resolve: (id: string) => void } {
  const [modelChoice, setModelChoice] = useState<string | null>(() => readStored(MODEL_STORAGE_KEY));
  const pick = useCallback((id: string): void => {
    writeStored(MODEL_STORAGE_KEY, id);
    setModelChoice(id);
  }, []);
  return { modelChoice, pick, resolve: setModelChoice };
}
