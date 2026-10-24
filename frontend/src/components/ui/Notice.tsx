import type { ReactNode } from "react";
import { InfoIcon, WarningIcon } from "./icons";

/** One notice style: border (warn border for warnings), 16px SVG icon at inline-start (spec 3.8). */
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
      {warning ? <WarningIcon /> : <InfoIcon />}
      <div>{children}</div>
    </div>
  );
}
