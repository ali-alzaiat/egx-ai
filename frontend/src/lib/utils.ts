import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/** tailwind-merge must know our type scale (tailwind.css), or text-ui would be read as a colour and dropped. */
const twMerge = extendTailwindMerge({
  extend: { classGroups: { "font-size": [{ text: ["ui", "table", "meta"] }] } },
});

/** Joins class names, letting a later Tailwind class win over a clashing earlier one. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
