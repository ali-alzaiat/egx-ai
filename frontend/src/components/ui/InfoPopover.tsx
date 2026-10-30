import type { ReactNode } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/shadcn/popover";
import { InfoIcon } from "./icons";

/** An `i` button that opens a short definition (max 320px). Escape or an outside click closes it (spec 3.10). */
export function InfoPopover({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={label}
          className="inline-flex size-7 items-center justify-center rounded-full border-0 bg-transparent text-muted-foreground align-middle hover:bg-accent hover:text-foreground"
        >
          <InfoIcon size={16} />
        </button>
      </PopoverTrigger>
      <PopoverContent className="[&_ul]:mt-2 [&_ul]:ps-5">{children}</PopoverContent>
    </Popover>
  );
}
