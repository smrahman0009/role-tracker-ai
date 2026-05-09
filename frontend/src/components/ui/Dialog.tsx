/**
 * Dialog — modal wrapper using Radix UI primitives.
 *
 * Used for confirmations like "Regenerate this letter? You'll lose the
 * current strategy." Includes a backdrop, escape-to-close, focus trap,
 * and accessible labelling by default.
 *
 * Usage:
 *   <Dialog open={isOpen} onOpenChange={setIsOpen}>
 *     <DialogContent>
 *       <DialogHeader>
 *         <DialogTitle>Regenerate?</DialogTitle>
 *         <DialogDescription>This discards the current strategy.</DialogDescription>
 *       </DialogHeader>
 *       <DialogFooter>
 *         <Button variant="secondary" onClick={() => setIsOpen(false)}>Cancel</Button>
 *         <Button onClick={handleRegenerate}>Regenerate</Button>
 *       </DialogFooter>
 *     </DialogContent>
 *   </Dialog>
 */

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import * as React from "react";

import { usePortalContainer } from "@/lib/portalContainer";
import { cn } from "@/lib/utils";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
/** Wraps Radix's Portal so the dialog renders into the
 *  PortalContainerContext target when set (e.g. the Picture-in-
 *  Picture window's body). Without this, dialogs opened from
 *  inside the PiP would render invisibly in the main window. */
export const DialogPortal = (
  props: React.ComponentProps<typeof DialogPrimitive.Portal>,
) => {
  const container = usePortalContainer();
  return <DialogPrimitive.Portal container={container} {...props} />;
};
export const DialogClose = DialogPrimitive.Close;

const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm",
      "data-[state=open]:animate-in data-[state=open]:fade-in-0",
      "data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
      className,
    )}
    {...props}
  />
));
DialogOverlay.displayName = "DialogOverlay";

export const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2",
        "w-full max-w-md rounded-xl bg-white border border-slate-200 shadow-md",
        "p-6",
        "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
        "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
        className,
      )}
      {...props}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4 rounded p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500/20">
        <X className="h-4 w-4" />
        <span className="sr-only">Close</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPortal>
));
DialogContent.displayName = "DialogContent";

export const DialogHeader = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("space-y-1.5 mb-4", className)} {...props} />
);
DialogHeader.displayName = "DialogHeader";

export const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn("text-base font-semibold text-slate-900", className)}
    {...props}
  />
));
DialogTitle.displayName = "DialogTitle";

export const DialogDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn("text-sm text-slate-600", className)}
    {...props}
  />
));
DialogDescription.displayName = "DialogDescription";

export const DialogFooter = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn("flex justify-end gap-2 mt-6", className)}
    {...props}
  />
);
DialogFooter.displayName = "DialogFooter";
