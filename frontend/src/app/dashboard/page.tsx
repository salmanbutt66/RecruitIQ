"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { getDashboardStats } from "@/lib/api";

export default function DashboardPage() {
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: getDashboardStats,
  });

  return (
    <AuthGuard>
      <AppShell>
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="mt-1 text-[var(--muted)]">Overview of your recruitment pipeline</p>
        </div>

        {isLoading && <p className="text-[var(--muted)]">Loading stats...</p>}
        {error && (
          <p className="text-[var(--danger)]">
            {error instanceof Error ? error.message : "Failed to load dashboard"}
          </p>
        )}

        {stats && (
          <>
            <div className="stat-grid mb-8">
              <div className="stat-card">
                <p>Open positions</p>
                <p>{stats.open_positions}</p>
              </div>
              <div className="stat-card">
                <p>Total candidates</p>
                <p>{stats.total_candidates}</p>
              </div>
              <div className="stat-card">
                <p>Shortlisted</p>
                <p className="text-[var(--success)]">{stats.shortlisted}</p>
              </div>
              <div className="stat-card">
                <p>In interview</p>
                <p className="text-[var(--accent-hover)]">{stats.in_interview}</p>
              </div>
              <div className="stat-card">
                <p>Rejected</p>
                <p className="text-[var(--danger)]">{stats.rejected}</p>
              </div>
              <div className="stat-card">
                <p>Pending offers</p>
                <p className="text-[var(--warning)]">{stats.offers_pending}</p>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <Link href="/positions" className="card p-6 transition hover:border-[var(--accent)]">
                <h2 className="font-semibold text-white">Manage positions</h2>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  Create jobs, upload resumes, and run AI screening
                </p>
              </Link>
              <Link href="/interviews" className="card p-6 transition hover:border-[var(--accent)]">
                <h2 className="font-semibold text-white">Interview batches</h2>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  Schedule panels and track evaluations
                </p>
              </Link>
              <Link href="/offers" className="card p-6 transition hover:border-[var(--accent)]">
                <h2 className="font-semibold text-white">Offers</h2>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  Draft, send, and track offer letters
                </p>
              </Link>
            </div>
          </>
        )}
      </AppShell>
    </AuthGuard>
  );
}
