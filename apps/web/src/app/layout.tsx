import type { Metadata, Viewport } from "next";
import { Inter, Press_Start_2P } from "next/font/google";
import "./globals.css";

const pixel = Press_Start_2P({ weight: "400", subsets: ["latin"], variable: "--font-pixel" });
const sans = Inter({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "Questboard",
  description: "Your daily, weekly and monthly quests.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "Questboard", statusBarStyle: "black-translucent" },
  icons: {
    icon: "/icons/icon-192.png",
    apple: "/icons/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  themeColor: "#1b1a2e",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${pixel.variable} ${sans.variable}`}>
      <body>{children}</body>
    </html>
  );
}
