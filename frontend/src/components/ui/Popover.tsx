/**
 * Popover — wraps Radix Popover with our card styling. Used for the
 * filter-chip dropdowns on Job List.
 */

import * as PopoverPrimitive from "@radix-ui/react-popover";
import * as React from "react";

import { usePortalContainer } from "@/lib/portalContainer";
import { cn } from "@/lib/utils";

export const Popover = PopoverPrimitive.Root;
export const PopoverTrigger = PopoverPrimitive.Trigger;

export const PopoverContent = React.forwardRef<
  React.ElementRef<typeof PopoverPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Content>
>(({ className, align = "start", sideOffset = 6, ...props }, ref) => {
  // Same PiP-aware portal trick as Dialog — see lib/portalContainer.tsx.
  const container = usePortalContainer();
  return (
    <PopoverPrimitive.Portal container={container}>
    <PopoverPrimitive.Content
      ref={ref}
      align={align}
      sideOffset={sideOffset}
      className={cn(
        "z-50 rounded-lg border border-slate-200 bg-white p-3 shadow-lg",
        "outline-none focus:outline-none",
        "data-[state=open]:animate-in data-[state=closed]:animate-out",
        "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
        className,
      )}
      {...props}
    />
    </PopoverPrimitive.Portal>
  );
});
PopoverContent.displayName = "PopoverContent";
