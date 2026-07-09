import type { Metadata } from "next";
import Image from "next/image";
import { Providers } from "@/components/Providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "RecruitIQ",
  description: "AI-powered recruitment platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
        <Image
          src="/ptcl-logo.png"
          alt="PTCL"
          width={90}
          height={38}
          className="fixed bottom-4 right-4 z-50 opacity-90 pointer-events-none select-none"
        />
      </body>
    </html>
  );
}