import { useEffect, useState } from "react";
import { readChartPalette, samePalette, type ChartPalette } from "../../lib/chartPalette";

function readFromRoot(): ChartPalette {
  const style = getComputedStyle(document.documentElement);
  return readChartPalette((token) => style.getPropertyValue(token));
}

/**
 * The chart's colours and font, read from the CSS tokens. They are read again when the theme changes
 * (the `data-theme` attribute, or the OS preference while no attribute is set) and when the language
 * changes (the font family follows `html[lang]`).
 */
export function usePriceChartPalette(): ChartPalette {
  const [palette, setPalette] = useState<ChartPalette>(readFromRoot);

  useEffect(() => {
    const refresh = (): void => {
      const next = readFromRoot();
      setPalette((prev) => (samePalette(prev, next) ? prev : next));
    };
    const observer = new MutationObserver(refresh);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "lang", "class"] });
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", refresh);
    // Tokens may differ from the first read if a stylesheet or font finished loading since.
    refresh();
    return () => {
      observer.disconnect();
      media.removeEventListener("change", refresh);
    };
  }, []);

  return palette;
}
