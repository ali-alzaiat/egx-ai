import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { ToggleGroup as ToggleGroupPrimitive } from "radix-ui";

import { cn } from "@/lib/utils";

/** Segmented-control sizes: `default` is control-h tall, `sm` is the compact sidebar form. */
const toggleGroupVariants = cva(
  "inline-flex max-w-full self-start overflow-hidden rounded-sm border border-input has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-ring",
  {
    variants: {
      size: {
        default: "min-h-11",
        sm: "min-h-8",
      },
    },
    defaultVariants: { size: "default" },
  },
);

const toggleGroupItemVariants = cva(
  "min-w-0 flex-auto border-0 bg-transparent py-1 font-medium text-text-2 outline-none hover:bg-accent data-[state=on]:bg-brand-bg data-[state=on]:font-semibold data-[state=on]:text-primary [&:not(:first-child)]:border-s [&:not(:first-child)]:border-input",
  {
    variants: {
      size: {
        default: "px-3 text-table md:px-4",
        sm: "px-3 text-meta",
      },
    },
    defaultVariants: { size: "default" },
  },
);

type ToggleGroupProps = Omit<
  React.ComponentProps<typeof ToggleGroupPrimitive.Root>,
  "type" | "value" | "defaultValue" | "onValueChange"
> &
  VariantProps<typeof toggleGroupVariants> & {
    value: string;
    onValueChange: (value: string) => void;
  };

const ToggleGroupContext = React.createContext<VariantProps<typeof toggleGroupItemVariants>>({ size: "default" });

/** Single-select group. Arrow keys follow the reading direction (Radix reads it from the Direction provider). */
function ToggleGroup({ className, size, value, onValueChange, children, ...props }: ToggleGroupProps) {
  return (
    <ToggleGroupPrimitive.Root
      data-slot="toggle-group"
      type="single"
      value={value}
      // Clicking the pressed item reports "": a segmented control always keeps one choice.
      onValueChange={(next) => {
        if (next !== "") onValueChange(next);
      }}
      className={cn(toggleGroupVariants({ size }), className)}
      {...props}
    >
      <ToggleGroupContext.Provider value={{ size }}>{children}</ToggleGroupContext.Provider>
    </ToggleGroupPrimitive.Root>
  );
}

function ToggleGroupItem({ className, ...props }: React.ComponentProps<typeof ToggleGroupPrimitive.Item>) {
  const { size } = React.useContext(ToggleGroupContext);
  return (
    <ToggleGroupPrimitive.Item
      data-slot="toggle-group-item"
      className={cn(toggleGroupItemVariants({ size }), className)}
      {...props}
    />
  );
}

export { ToggleGroup, ToggleGroupItem };
