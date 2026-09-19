import type { Metadata } from "next";
import { Hanken_Grotesk, Manrope } from "next/font/google";
import type { ReactNode } from "react";
import { Providers } from "@/lib/session";
import { cn } from "@/lib/utils";
import "./globals.css";

// Body and tables: Hanken Grotesk. Headings and headline figures: Manrope, whose geometric forms echo the logo.
const body = Hanken_Grotesk({ subsets: ["latin"], variable: "--font-body", display: "swap" });
const display = Manrope({ subsets: ["latin"], variable: "--font-display", display: "swap" });

export const metadata: Metadata = {
  title: { default: "PredictaX", template: "%s · PredictaX" },
  description: "Demand intelligence for automobile dealer groups",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={cn("font-sans", body.variable, display.variable)} suppressHydrationWarning>
      <body className="min-h-screen antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
