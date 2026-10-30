import type { ReactNode } from "react";
import { Alert } from "@/components/shadcn/alert";
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
    <Alert variant={warning ? "warning" : "default"} role={warning ? "alert" : "note"}>
      {warning ? <WarningIcon size={20} /> : <InfoIcon size={20} />}
      <div>{children}</div>
    </Alert>
  );
}
