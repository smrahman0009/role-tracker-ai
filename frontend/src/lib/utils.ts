/**
 * Utility helpers used by every UI component.
 */

import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Smart className merger. Combines clsx (conditional classes) with
 * tailwind-merge (resolves conflicts between Tailwind utilities, e.g.
 * `bg-red-500 bg-blue-500` → just `bg-blue-500`).
 *
 * Standard shadcn/ui convention. Used by every component.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
