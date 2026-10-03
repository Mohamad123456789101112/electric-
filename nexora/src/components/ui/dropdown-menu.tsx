"use client";

import * as DropdownPrimitive from "@radix-ui/react-dropdown-menu";
import { Check, ChevronLeft } from "lucide-react";
import { cn } from "@/lib/utils";

export const DropdownMenu = DropdownPrimitive.Root;
export const DropdownMenuTrigger = DropdownPrimitive.Trigger;
export const DropdownMenuGroup = DropdownPrimitive.Group;
export const DropdownMenuSub = DropdownPrimitive.Sub;
export const DropdownMenuRadioGroup = DropdownPrimitive.RadioGroup;

export function DropdownMenuContent({ className, sideOffset = 6, ...props }: DropdownPrimitive.DropdownMenuContentProps) {
  return (
    <DropdownPrimitive.Portal>
      <DropdownPrimitive.Content
        sideOffset={sideOffset}
        className={cn(
          "z-50 min-w-[12rem] overflow-hidden rounded-[var(--radius-md)] border border-border bg-paper p-1.5 shadow-[var(--shadow-elevation-2)] data-[state=open]:animate-scale-in",
          className
        )}
        {...props}
      />
    </DropdownPrimitive.Portal>
  );
}

export function DropdownMenuItem({ className, ...props }: DropdownPrimitive.DropdownMenuItemProps) {
  return (
    <DropdownPrimitive.Item
      className={cn(
        "flex cursor-pointer select-none items-center gap-2 rounded-[var(--radius-sm)] px-2.5 py-2 text-sm text-ink outline-none transition-colors focus:bg-surface data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        className
      )}
      {...props}
    />
  );
}

export function DropdownMenuCheckboxItem({ className, children, checked, ...props }: DropdownPrimitive.DropdownMenuCheckboxItemProps) {
  return (
    <DropdownPrimitive.CheckboxItem
      checked={checked}
      className={cn(
        "flex cursor-pointer select-none items-center gap-2 rounded-[var(--radius-sm)] py-2 pe-2.5 ps-7 text-sm text-ink outline-none transition-colors focus:bg-surface relative",
        className
      )}
      {...props}
    >
      <DropdownPrimitive.ItemIndicator className="absolute end-auto start-2 inline-flex items-center">
        <Check className="h-3.5 w-3.5" />
      </DropdownPrimitive.ItemIndicator>
      {children}
    </DropdownPrimitive.CheckboxItem>
  );
}

export function DropdownMenuLabel({ className, ...props }: DropdownPrimitive.DropdownMenuLabelProps) {
  return <DropdownPrimitive.Label className={cn("px-2.5 py-1.5 text-xs font-medium text-ink-muted", className)} {...props} />;
}

export function DropdownMenuSeparator({ className, ...props }: DropdownPrimitive.DropdownMenuSeparatorProps) {
  return <DropdownPrimitive.Separator className={cn("my-1 h-px bg-border", className)} {...props} />;
}

export function DropdownMenuSubTrigger({ className, children, ...props }: DropdownPrimitive.DropdownMenuSubTriggerProps) {
  return (
    <DropdownPrimitive.SubTrigger
      className={cn(
        "flex cursor-pointer select-none items-center justify-between rounded-[var(--radius-sm)] px-2.5 py-2 text-sm text-ink outline-none transition-colors focus:bg-surface",
        className
      )}
      {...props}
    >
      {children}
      <ChevronLeft className="h-3.5 w-3.5 text-ink-muted" />
    </DropdownPrimitive.SubTrigger>
  );
}

export function DropdownMenuSubContent({ className, ...props }: DropdownPrimitive.DropdownMenuSubContentProps) {
  return (
    <DropdownPrimitive.Portal>
      <DropdownPrimitive.SubContent
        className={cn(
          "z-50 min-w-[10rem] overflow-hidden rounded-[var(--radius-md)] border border-border bg-paper p-1.5 shadow-[var(--shadow-elevation-2)] data-[state=open]:animate-scale-in",
          className
        )}
        {...props}
      />
    </DropdownPrimitive.Portal>
  );
}
