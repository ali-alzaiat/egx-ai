import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const alertVariants = cva(
  "flex items-start gap-3 rounded-md border bg-card p-[var(--card-pad)] text-ui text-card-foreground [&>svg]:mt-0.5 [&>svg]:flex-none",
  {
    variants: {
      variant: {
        default: "border-border [&>svg]:text-text-2",
        warning: "border-warn bg-warn-bg [&>svg]:text-warn",
        destructive: "border-destructive text-destructive",
        success: "border-gain text-gain",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

function Alert({ className, variant, ...props }: React.ComponentProps<"div"> & VariantProps<typeof alertVariants>) {
  return <div data-slot="alert" className={cn(alertVariants({ variant }), className)} {...props} />;
}

export { Alert, alertVariants };
