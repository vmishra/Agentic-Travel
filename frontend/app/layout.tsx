import type { Metadata } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import { Fraunces } from "next/font/google";
import "./globals.css";

const display = Fraunces({
  subsets: ["latin"],
  style: ["normal", "italic"],
  axes: ["opsz", "SOFT"],
  variable: "--font-display",
});

export const metadata: Metadata = {
  title: "Agentic Travel — a private travel concierge",
  description:
    "A concierge that composes bookable, considered itineraries — flights, stays, dining, day-by-day, with the work shown.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      data-theme="dark"
      className={`${GeistSans.variable} ${GeistMono.variable} ${display.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
