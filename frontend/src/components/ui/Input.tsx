/**
 * Input — text/email/url/tel/number/password fields.
 *
 * Single component for all `<input>` types — pass `type` like a normal
 * input. Tailwind classes locked to the design system: 8px radius, slate
 * borders, indigo-500 focus ring at 20% opacity.
 */

import * as React from "react";

import { cn } from "@/lib/utils";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type = "text", ...props }, ref) => (
    <input
      type={type}
      ref={ref}
      className={cn(
        "w-full rounded-lg bg-white border border-slate-200",
        "px-3 py-2 text-sm text-slate-900",
        "placeholder:text-slate-400",
        "focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500",
        "disabled:bg-slate-50 disabled:text-slate-400 disabled:cursor-not-allowed",
        "transition-colors duration-150",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";


/**
 * Textarea — multi-line variant of Input. Same focus / disabled
 * behavior. Defaults to non-resizable since most text areas in this
 * app live inside cards with fixed widths.
 */
export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, rows = 3, ...props }, ref) => (
    <textarea
      ref={ref}
      rows={rows}
      className={cn(
        "w-full rounded-lg bg-white border border-slate-200",
        "px-3 py-2 text-sm text-slate-900",
        "placeholder:text-slate-400 resize-none",
        "focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500",
        "disabled:bg-slate-50 disabled:text-slate-400 disabled:cursor-not-allowed",
        "transition-colors duration-150",
        className,
      )}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";


/**
 * Label — paired with Input to give the field a visible label.
 * Use `htmlFor` to match the input's `id` for accessibility.
 */
export const Label = React.forwardRef<
  HTMLLabelElement,
  React.LabelHTMLAttributes<HTMLLabelElement>
>(({ className, ...props }, ref) => (
  <label
    ref={ref}
    className={cn("block text-xs font-medium text-slate-700", className)}
    {...props}
  />
));
Label.displayName = "Label";
