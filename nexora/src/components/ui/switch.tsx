"use client";

import * as SwitchPrimitive from "@radix-ui/react-switch";
import { cn } from "@/lib/utils";

export function Switch({ className, ...props }: SwitchPrimitive.SwitchProps) {
  return (
    <SwitchPrimitive.Root
      className={cn(
        "relative h-6 w-11 shrink-0 rounded-full bg-surface-strong transition-colors data-[state=checked]:bg-accent",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50",
        className
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb className="block h-5 w-5 rounded-full bg-white shadow transition-transform ltr:translate-x-0.5 rtl:-translate-x-0.5 ltr:data-[state=checked]:translate-x-[22px] rtl:data-[state=checked]:-translate-x-[22px]" />
    </SwitchPrimitive.Root>
  );
}
