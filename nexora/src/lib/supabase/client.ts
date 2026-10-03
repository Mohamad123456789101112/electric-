"use client";

// =============================================================================
// Browser Supabase client.
// Only ever constructed with the PUBLIC url + anon key. The anon key is safe
// to ship to the browser by design — every table it can touch is protected by
// Row Level Security, so it is never a source of truth for authorization.
// =============================================================================
import { createBrowserClient } from "@supabase/ssr";

function getEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `Missing ${name}. Copy .env.example to .env.local and fill in your Supabase project settings.`
    );
  }
  return value;
}

export function createClient() {
  return createBrowserClient(
    getEnv("NEXT_PUBLIC_SUPABASE_URL"),
    getEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
  );
}
