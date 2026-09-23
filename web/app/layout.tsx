import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Apartment Hunter",
  description: "Apartamentos en alquiler que cumplen tus criterios.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className="min-h-screen antialiased font-sans">{children}</body>
    </html>
  );
}
