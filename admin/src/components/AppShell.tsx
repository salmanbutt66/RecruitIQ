"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearTokens } from "@/lib/api";

const links = [
  { href: "/organizations", label: "Organizations" },
  { href: "/audit-logs", label: "Audit Logs" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <div className="min-h-screen">
      <header className="border-b border-[var(--border)] bg-[rgba(18,24,41,0.8)] backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-8">
            <Link href="/organizations" className="text-xl font-bold text-white">
              Recruit<span className="text-[var(--accent)]">IQ</span>
              <span className="ml-2 text-sm font-normal text-[var(--muted)]">Admin</span>
            </Link>
            <nav className="hidden gap-4 md:flex">
              {links.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`text-sm font-medium ${
                    pathname.startsWith(link.href) ? "text-white" : "text-[var(--muted)] hover:text-white"
                  }`}
                >
                  {link.label}
                </Link>
              ))}
            </nav>
          </div>
          <button
            className="btn btn-primary text-sm"
            onClick={() => {
              clearTokens();
              router.push("/login");
            }}
          >
            Sign out
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
    </div>
  );
}
