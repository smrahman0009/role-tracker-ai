/**
 * Button — primary, secondary, ghost, and destructive variants.
 *
 * Uses class-variance-authority (cva) to define discrete variant sets
 * that combine cleanly. Pass `variant` and `size` props to pick.
 *
 * Tailwind classes locked to the design system (docs/wireframes/design_system.md):
 * primary uses indigo-600, all variants use 200ms ease-out transitions,
 * focus rings are indigo-500/20.
 */

import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  // Base — applied to every button regardless of variant.
  [
    "inline-flex items-center justify-center gap-1.5",
    "rounded-lg font-medium",
    "transition-colors duration-150",
    "focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:ring-offset-0",
    "disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none",
    "[&_svg]:shrink-0",
  ],
  {
    variants: {
      variant: {
        primary: [
          "bg-indigo-600 text-white",
          "hover:bg-indigo-700",
          "active:bg-indigo-800",
          "disabled:bg-slate-300",
        ],
        secondary: [
          "bg-white text-slate-700 border border-slate-200",
          "hover:bg-slate-50 hover:border-slate-300",
          "active:bg-slate-100",
        ],
        ghost: [
          "text-slate-600 bg-transparent",
          "hover:bg-slate-100 hover:text-slate-900",
        ],
        destructive: [
          "bg-rose-600 text-white",
          "hover:bg-rose-700",
          "active:bg-rose-800",
        ],
        link: [
          "text-indigo-600 underline-offset-4",
          "hover:text-indigo-700 hover:underline",
        ],
      },
      size: {
        sm: "h-8 px-3 text-xs [&_svg]:h-3.5 [&_svg]:w-3.5",
        md: "h-9 px-4 text-sm [&_svg]:h-4 [&_svg]:w-4",
        lg: "h-10 px-5 text-sm [&_svg]:h-4 [&_svg]:w-4",
        icon: "h-9 w-9 [&_svg]:h-4 [&_svg]:w-4",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** Render as a different element (e.g. an anchor) via Radix Slot. */
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { buttonVariants };
