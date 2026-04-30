/**
 * usePictureInPictureWindow — wraps the Document Picture-in-Picture API
 * (Chrome/Edge 116+) so a React component can render itself into a
 * floating, always-on-top OS window via createPortal.
 *
 * Flow:
 *   const pip = usePictureInPictureWindow();
 *   const open = () => pip.open({ width: 380, height: 900 });
 *   {pip.pipWindow && createPortal(<KitContents/>, pip.pipWindow.document.body)}
 *
 * What this handles:
 *   - Feature detection (Safari/Firefox return isSupported=false).
 *   - Cloning stylesheets from the main document so Tailwind classes
 *     work in the PiP DOM (the PiP window is a fresh document with no
 *     CSS by default).
 *   - Tracking the window's open/close state so React re-renders.
 *   - Cleanup on unmount.
 *
 * What this doesn't handle:
 *   - Re-applying styles when Tailwind hot-reloads in dev. Reopen the
 *     PiP window after a style change to pick up new rules.
 */

import { useCallback, useEffect, useState } from "react";

interface DocumentPictureInPicture {
  requestWindow(options?: { width?: number; height?: number }): Promise<Window>;
}

declare global {
  interface Window {
    documentPictureInPicture?: DocumentPictureInPicture;
  }
}

interface OpenOptions {
  width?: number;
  height?: number;
}

export function usePictureInPictureWindow() {
  const [pipWindow, setPipWindow] = useState<Window | null>(null);

  const isSupported =
    typeof window !== "undefined" && "documentPictureInPicture" in window;

  const open = useCallback(
    async (options: OpenOptions = {}): Promise<Window | null> => {
      if (!isSupported || !window.documentPictureInPicture) return null;

      const w = await window.documentPictureInPicture.requestWindow({
        width: options.width ?? 380,
        height: options.height ?? 900,
      });

      // Copy every stylesheet from the main document so Tailwind +
      // component styles resolve correctly inside the PiP window.
      for (const sheet of Array.from(document.styleSheets)) {
        try {
          const rules = Array.from(sheet.cssRules)
            .map((rule) => rule.cssText)
            .join("\n");
          const style = w.document.createElement("style");
          style.textContent = rules;
          w.document.head.appendChild(style);
        } catch {
          // Cross-origin stylesheets throw on cssRules access; clone
          // the <link> so the PiP window fetches it itself.
          if (sheet.href) {
            const link = w.document.createElement("link");
            link.rel = "stylesheet";
            link.href = sheet.href;
            w.document.head.appendChild(link);
          }
        }
      }

      // Match our app's body styling so the PiP window doesn't render
      // on a stark white default background.
      w.document.body.classList.add("bg-slate-50");
      w.document.body.style.margin = "0";

      // The browser fires `pagehide` when the user closes the PiP window.
      const handleClose = () => setPipWindow(null);
      w.addEventListener("pagehide", handleClose);

      setPipWindow(w);
      return w;
    },
    [isSupported],
  );

  const close = useCallback(() => {
    pipWindow?.close();
    setPipWindow(null);
  }, [pipWindow]);

  // Close any open PiP window when the host component unmounts (e.g.,
  // user navigates away from the Job Detail page).
  useEffect(() => {
    return () => {
      pipWindow?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { isSupported, pipWindow, open, close };
}
