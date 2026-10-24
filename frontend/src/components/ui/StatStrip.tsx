import type { ReactNode } from "react";

export interface StatItem {
  id: string;
  label: string;
  value: ReactNode;
  /** Small line under the value. */
  sub?: ReactNode;
  /** Larger figure for the lead item. */
  hero?: boolean;
  /** Numeric values are shown LTR with tabular digits. */
  numeric?: boolean;
}

/** Items separated by inline dividers; 2-column grid on small screens (spec 3.5). No cards, no icons. */
export function StatStrip({ items, label }: { items: readonly StatItem[]; label?: string }) {
  return (
    <ul className="stat-strip" aria-label={label}>
      {items.map((item) => (
        <li key={item.id} className={`stat-item${item.hero ? " stat-item-hero" : ""}`}>
          <span className="stat-label">{item.label}</span>
          <span className="stat-value" {...(item.numeric ? { dir: "ltr" } : {})}>
            {item.value}
          </span>
          {item.sub && <span className="stat-sub">{item.sub}</span>}
        </li>
      ))}
    </ul>
  );
}
