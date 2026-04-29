/**
 * Tabs — wraps Radix UI's accessible tabs primitive with our design tokens.
 *
 * The "underline" style matches the filter tabs in the Job List mockup:
 * 2px indigo-600 underline on the active tab, transparent on inactive
 * (so the layout doesn't shift). Supports keyboard nav out of the box
 * via Radix.
 *
 * Usage:
 *   <Tabs defaultValue="unapplied">
 *     <TabsList>
 *       <TabsTrigger value="unapplied">Unapplied</TabsTrigger>
 *       <TabsTrigger value="all">All</TabsTrigger>
 *     </TabsList>
 *     <TabsContent value="unapplied">...</TabsContent>
 *     <TabsContent value="all">...</TabsContent>
 *   </Tabs>
 */

import * as TabsPrimitive from "@radix-ui/react-tabs";
import * as React from "react";

import { cn } from "@/lib/utils";

export const Tabs = TabsPrimitive.Root;

export const TabsList = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn("flex items-center gap-1 border-b border-slate-200", className)}
    {...props}
  />
));
TabsList.displayName = "TabsList";

export const TabsTrigger = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      "px-4 py-2.5 -mb-px",
      "text-sm font-medium text-slate-500",
      "border-b-2 border-transparent",
      "hover:text-slate-700",
      "transition-colors duration-150",
      "focus:outline-none focus:ring-2 focus:ring-indigo-500/20 rounded-t-sm",
      "data-[state=active]:text-slate-900 data-[state=active]:border-indigo-600",
      className,
    )}
    {...props}
  />
));
TabsTrigger.displayName = "TabsTrigger";

export const TabsContent = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn(
      "mt-4 focus:outline-none focus:ring-2 focus:ring-indigo-500/20",
      className,
    )}
    {...props}
  />
));
TabsContent.displayName = "TabsContent";
