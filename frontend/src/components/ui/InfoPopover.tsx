import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { InfoIcon } from "./icons";
import "./InfoPopover.css";

/** An `i` button that opens a short definition (max 320px). Escape or an outside click closes it (spec 3.10). */
export function InfoPopover({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLSpanElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent): void => {
      if (rootRef.current && e.target instanceof Node && !rootRef.current.contains(e.target)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent): void => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <span className="info-popover" ref={rootRef}>
      <button
        type="button"
        className="info-popover-btn"
        aria-label={label}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((v) => !v)}
      >
        <InfoIcon size={16} />
      </button>
      {open && (
        <div id={id} className="info-popover-body" role="note">
          {children}
        </div>
      )}
    </span>
  );
}
