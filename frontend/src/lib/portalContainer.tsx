/**
 * PortalContainerContext — tells Radix-portal-using components which
 * document body to portal into.
 *
 * Why this exists: Document Picture-in-Picture creates a separate
 * `Window` with its own `document`. React's `createPortal` can render
 * into the PiP document, but Radix's `Portal` primitive doesn't know
 * about it — by default it portals to the *original* document.body.
 *
 * Result without this context: a button clicked inside the PiP window
 * opens a Dialog that renders invisibly in the main window. The
 * user sees nothing happen.
 *
 * Fix: provide the PiP window's `document.body` via this context;
 * Radix-portal-using components read it and pass it as the
 * `container` prop on their internal `Portal`. When unset (the
 * normal case in the main window), Radix falls back to its default
 * `document.body`.
 *
 * Affected components: Dialog, Popover, Toaster, anything else that
 * uses a Radix `Portal` under the hood.
 */

import { createContext, useContext, type ReactNode } from "react";

const PortalContainerContext = createContext<HTMLElement | undefined>(
  undefined,
);

interface ProviderProps {
  /** The element to use as the portal container. Pass
   *  `pipWindow.document.body` when rendering inside a PiP. Pass
   *  undefined or omit to leave Radix's default behaviour intact. */
  container: HTMLElement | undefined;
  children: ReactNode;
}

export function PortalContainerProvider({ container, children }: ProviderProps) {
  return (
    <PortalContainerContext.Provider value={container}>
      {children}
    </PortalContainerContext.Provider>
  );
}

export function usePortalContainer(): HTMLElement | undefined {
  return useContext(PortalContainerContext);
}
