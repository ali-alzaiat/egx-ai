import type { FairValueInputs } from "../types";

/** One scalar (decimal-string) input of the fair value; the structured `fcfe_base` and gaps read as `null`. */
export function scalarInput(inputs: FairValueInputs, key: string): string | null {
  const value = inputs[key];
  return typeof value === "string" && value !== "" ? value : null;
}

/** Every scalar input that has a value, in payload order (the structured `fcfe_base` is excluded). */
export function scalarInputEntries(inputs: FairValueInputs): [string, string][] {
  return Object.entries(inputs).flatMap(([key, value]): [string, string][] =>
    typeof value === "string" && value !== "" ? [[key, value]] : [],
  );
}
