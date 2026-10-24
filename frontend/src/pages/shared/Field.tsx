import type { ReactNode } from "react";

/** Label above a control; the control is the label's child so a click focuses it. */
export function Field({ label, hint, children }: { label: ReactNode; hint?: string; children: ReactNode }) {
  return (
    <label className="fld">
      <span className="fld-label">{label}</span>
      {children}
      {hint ? <span className="fld-hint">{hint}</span> : null}
    </label>
  );
}

/** Label for a control that cannot sit inside a `<label>` (the company picker). */
export function FieldGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="fld" role="group" aria-label={label}>
      <span className="fld-label">{label}</span>
      {children}
    </div>
  );
}
