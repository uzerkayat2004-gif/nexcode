import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'NexCode - AI-Powered Coding Assistant',
  description: 'The open, multi-provider agentic coding CLI and web app',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#0a0a0f] text-gray-100 antialiased">
        {children}
      </body>
    </html>
  );
}
