"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getMe, getToken } from "@/lib/api";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    async function checkAuth() {
      if (!getToken()) {
        router.replace("/login");
        return;
      }

      try {
        const user = await getMe();
        if (user.role !== "platform_admin") {
          router.replace("/login");
          return;
        }
        setReady(true);
      } catch {
        router.replace("/login");
      }
    }

    checkAuth();
  }, [router]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-[var(--muted)]">Loading...</p>
      </div>
    );
  }

  return <>{children}</>;
}
