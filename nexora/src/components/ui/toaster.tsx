"use client";

import { Toaster as SonnerToaster } from "sonner";

export function Toaster() {
  return (
    <SonnerToaster
      position="top-center"
      dir="rtl"
      toastOptions={{
        style: {
          fontFamily: "var(--font-cairo)",
          borderRadius: "0.625rem",
          border: "1px solid var(--color-border)",
        },
      }}
    />
  );
}
