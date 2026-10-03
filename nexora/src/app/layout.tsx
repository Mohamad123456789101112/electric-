import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

// Self-hosted variable Cairo font (OFL-licensed, see src/app/fonts/OFL.txt).
// Using next/font/local instead of next/font/google avoids a build-time
// network dependency on Google Fonts entirely — the font ships with the app
// bundle, which is both more robust (works in offline/restricted CI/build
// environments) and marginally better for privacy than fetching from Google
// at request time.
const cairo = localFont({
  src: "./fonts/Cairo-Variable.ttf",
  weight: "200 1000",
  variable: "--font-cairo",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "NEXORA — نظام التشغيل الذكي للتعليم الحديث",
    template: "%s | NEXORA",
  },
  description:
    "NEXORA توحّد إدارة الطلاب والحضور والواجبات والدرجات والمدفوعات والتحليلات في منصة واحدة ذكية وآمنة للمعلمين والأكاديميات.",
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#ffffff",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl" className={cairo.variable}>
      <body className="min-h-screen bg-paper font-sans text-ink antialiased">
        {children}
        <Toaster />
      </body>
    </html>
  );
}
