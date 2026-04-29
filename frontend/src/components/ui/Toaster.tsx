/**
 * Toaster — wraps Sonner with our design system.
 *
 * Sonner is the modern toast library shadcn now recommends (replaced
 * their older custom Toast). Stacking, dismiss, theming, and
 * accessibility are all handled. We just style the container.
 *
 * Mount once at the app root:
 *   <App>
 *     <Toaster />
 *     <RouterProvider ... />
 *   </App>
 *
 * Use anywhere:
 *   import { toast } from "sonner";
 *   toast("Letter saved");
 *   toast.success("Generation complete");
 *   toast.error("Something went wrong");
 */

import { Toaster as SonnerToaster } from "sonner";

export const Toaster = () => (
  <SonnerToaster
    position="bottom-right"
    duration={4000}
    closeButton
    richColors
    toastOptions={{
      classNames: {
        toast:
          "rounded-lg border border-slate-200 bg-white shadow-md text-sm text-slate-900",
        title: "font-medium text-slate-900",
        description: "text-slate-600",
        actionButton:
          "bg-indigo-600 text-white hover:bg-indigo-700 transition-colors",
        cancelButton:
          "bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors",
      },
    }}
  />
);

// Re-export the toast() function so consumers don't have to import sonner directly.
export { toast } from "sonner";
