import type { ReactNode } from "react";
import { InfoIcon, WarningIcon } from "./icons";

/** One notice style: border (warn border for warnings), 20px SVG icon at inline-start, card padding (spec 3.8, friendly look). */
export function Notice({
  variant = "info",
  children,
}: {
  variant?: "info" | "warning";
  children: ReactNode;
}) {
  const warning = variant === "warning";
  return (
    <div className={`notice${warning ? " notice-warning" : ""}`} role={warning ? "alert" : "note"}>
      {warning ? <WarningIcon size={20} /> : <InfoIcon size={20} />}
      <div>{children}</div>
    </div>
  );
}
