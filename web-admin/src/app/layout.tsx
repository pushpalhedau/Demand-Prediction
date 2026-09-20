import type { Metadata } from "next";
import { Hanken_Grotesk, Manrope } from "next/font/google";
import type { ReactNode } from "react";
import { Providers } from "@/lib/session";
import { cn } from "@/lib/utils";
import "./globals.css";

const body = Hanken_Grotesk({ subsets: ["latin"], variable: "--font-body", display: "swap" });
const display = Manrope({ subsets: ["latin"], variable: "--font-display", display: "swap" });

export const metadata: Metadata = {
  title: { default: "PredictaX Admin", template: "%s · PredictaX Admin" },
  description: "Operator console for PredictaX",
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
