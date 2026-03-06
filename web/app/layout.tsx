import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NexCode — AI Coding Assistant",
  description: "AI-powered coding assistant that works everywhere. Like Claude Code, but open and multi-model.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
