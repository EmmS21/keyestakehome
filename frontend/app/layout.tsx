import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Data Cleaning Tool",
  description: "Upload deal CSVs and clean anomalies",
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
