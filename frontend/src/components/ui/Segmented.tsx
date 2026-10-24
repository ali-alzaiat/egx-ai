import { useRef, type KeyboardEvent } from "react";

export interface SegmentedOption<V extends string> {
  value: V;
  label: string;
  /** Own language tag: the language switch shows each option in its own language. */
  lang?: string;
}

/** Radio-group segmented control, control-h tall (spec 3.10). */
export function Segmented<V extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: readonly SegmentedOption<V>[];
  value: V;
  onChange: (value: V) => void;
  label: string;
}) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);

  const move = (from: number, step: number): void => {
    const next = (from + step + options.length) % options.length;
    const opt = options[next];
    if (!opt) return;
    onChange(opt.value);
    refs.current[next]?.focus();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>, index: number): void => {
    // Arrow keys follow the visual direction, which flips in RTL.
    const rtl = document.documentElement.dir === "rtl";
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      move(index, e.key === "ArrowRight" && rtl ? -1 : 1);
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      move(index, e.key === "ArrowLeft" && rtl ? 1 : -1);
    }
  };

  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {options.map((opt, i) => {
        const checked = opt.value === value;
        return (
          <button
            key={opt.value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={checked ? 0 : -1}
            lang={opt.lang}
            onClick={() => onChange(opt.value)}
            onKeyDown={(e) => onKeyDown(e, i)}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
