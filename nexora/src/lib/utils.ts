import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const arNumber = new Intl.NumberFormat("ar-EG");
const arCurrency = (currency: string) =>
  new Intl.NumberFormat("ar-EG", { style: "currency", currency, maximumFractionDigits: 2 });

export function formatNumber(value: number): string {
  return arNumber.format(value);
}

export function formatCurrency(value: number, currency = "EGP"): string {
  try {
    return arCurrency(currency).format(value);
  } catch {
    return `${formatNumber(value)} ${currency}`;
  }
}

export function formatDate(value: string | Date, opts: Intl.DateTimeFormatOptions = {}): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return new Intl.DateTimeFormat("ar-EG", { day: "numeric", month: "short", year: "numeric", ...opts }).format(date);
}

export function formatDateTime(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return new Intl.DateTimeFormat("ar-EG", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatRelativeTime(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  const diffMs = date.getTime() - Date.now();
  const diffMin = Math.round(diffMs / 60000);
  const rtf = new Intl.RelativeTimeFormat("ar-EG", { numeric: "auto" });

  if (Math.abs(diffMin) < 60) return rtf.format(diffMin, "minute");
  const diffHours = Math.round(diffMin / 60);
  if (Math.abs(diffHours) < 24) return rtf.format(diffHours, "hour");
  const diffDays = Math.round(diffHours / 24);
  if (Math.abs(diffDays) < 30) return rtf.format(diffDays, "day");
  const diffMonths = Math.round(diffDays / 30);
  if (Math.abs(diffMonths) < 12) return rtf.format(diffMonths, "month");
  return rtf.format(Math.round(diffMonths / 12), "year");
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "؟";
  if (parts.length === 1) return parts[0].slice(0, 2);
  return parts[0][0] + parts[1][0];
}

/**
 * Organization slugs are constrained at the database level to
 * ^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$ — ASCII only. Arabic organization names
 * are the common case, so we transliterate what we can and otherwise fall
 * back to a short random-but-stable suffix rather than producing an invalid
 * (or empty) slug.
 */
export function slugify(value: string): string {
  const base = value
    .trim()
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 40);

  const randomSuffix = Math.random().toString(36).slice(2, 7);

  if (base.length < 3) {
    return `org-${randomSuffix}`;
  }
  return `${base}-${randomSuffix}`;
}
