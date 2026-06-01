import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Edge Terminal — BTC · Altcoins · AI Bottleneck Stocks",
  description: "Live trading dashboard: daily bias + risk-on/off regime, BTC cycle, crypto perps/funding & altcoin short-squeeze scoring, and the AI bottleneck 5-layer stock framework with technical setups & options plays.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
