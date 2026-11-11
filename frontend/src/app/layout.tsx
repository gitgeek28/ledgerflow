import "./globals.css";

import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import type { Metadata } from "next";

import { Providers } from "@/components/layout/providers";

export const metadata: Metadata = {
  title: { default: "LedgerFlow", template: "%s · LedgerFlow" },
  description: "Intelligent accounts payable operations: from invoice PDF to an explainable AP decision.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body><Providers>{children}</Providers></body>
    </html>
  );
}
