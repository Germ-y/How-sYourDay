import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "How's Your Day",
  description: "Emotion-aware daily planning agent"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

