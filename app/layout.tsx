import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Cycle Edge Dashboard — BTC $4K→$50K",
  description: "Live BTC trading dashboard: Macro Regime Monitor, BTC Cycle Bottom Detector, Perp Short Signals, Options Flow, and Trade Tracker.",
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
