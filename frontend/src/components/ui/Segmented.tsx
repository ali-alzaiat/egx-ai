import { ToggleGroup, ToggleGroupItem } from "@/components/shadcn/toggle-group";

export interface SegmentedOption<V extends string> {
  value: V;
  label: string;
  /** Own language tag: the language switch shows each option in its own language. */
  lang?: string;
}

/**
 * Single-choice segmented control on the shadcn ToggleGroup (spec 3.10). Arrow keys move the choice, like a
 * radio group, and follow the reading direction. The `segmented` class is only a hook for page-level overrides.
 */
export function Segmented<V extends string>({
  options,
  value,
  onChange,
  label,
  size,
}: {
  options: readonly SegmentedOption<V>[];
  value: V;
  onChange: (value: V) => void;
  label: string;
  size?: "default" | "sm";
}) {
  const select = (next: string): void => {
    const opt = options.find((o) => o.value === next);
    if (opt) onChange(opt.value);
  };

  return (
    <ToggleGroup className="segmented" aria-label={label} size={size} value={value} onValueChange={select}>
      {options.map((opt) => (
        <ToggleGroupItem
          key={opt.value}
          value={opt.value}
          lang={opt.lang}
          // Arrow keys move focus; selecting on focus makes them move the choice, as a radio group does.
          onFocus={() => select(opt.value)}
        >
          {opt.label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}
