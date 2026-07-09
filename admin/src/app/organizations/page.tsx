"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { AdminOrganization, listOrganizations, suspendOrganization } from "@/lib/api";

function planBadge(plan: string | null) {
  if (!plan) return <span className="badge badge-muted">none</span>;
  return <span className="badge badge-warning">{plan}</span>;
}

function statusBadge(active: boolean) {
  return active ? (
    <span className="badge badge-success">active</span>
  ) : (
    <span className="badge badge-danger">suspended</span>
  );
}

function OrganizationRow({
  org,
  onSuspend,
  suspending,
}: {
  org: AdminOrganization;
  onSuspend: (id: string) => void;
  suspending: boolean;
}) {
  return (
    <tr>
      <td>
        <div className="font-medium text-white">{org.name}</div>
        <div className="text-sm text-[var(--muted)]">{org.slug}</div>
      </td>
      <td>{statusBadge(org.is_active)}</td>
      <td>{planBadge(org.subscription_plan)}</td>
      <td>{org.user_count}</td>
      <td>{org.resumes_used}</td>
      <td>
        <button
          className="btn btn-danger text-xs"
          disabled={!org.is_active || suspending}
          onClick={() => {
            if (confirm(`Suspend organization "${org.name}"? Users will lose access.`)) {
              onSuspend(org.id);
            }
          }}
        >
          Suspend
        </button>
      </td>
    </tr>
  );
}

export default function OrganizationsPage() {
  const queryClient = useQueryClient();
  const { data: orgs = [], isLoading, error } = useQuery({
    queryKey: ["admin-organizations"],
    queryFn: listOrganizations,
  });

  const suspendMutation = useMutation({
    mutationFn: suspendOrganization,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-organizations"] }),
  });

  const activeCount = orgs.filter((o) => o.is_active).length;
  const suspendedCount = orgs.length - activeCount;

  return (
    <AuthGuard>
      <AppShell>
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white">Organizations</h1>
          <p className="mt-1 text-[var(--muted)]">Manage tenant organizations on the platform</p>
        </div>

        <div className="mb-6 grid gap-4 sm:grid-cols-3">
          <div className="card p-4">
            <p className="text-sm text-[var(--muted)]">Total</p>
            <p className="text-2xl font-bold text-white">{orgs.length}</p>
          </div>
          <div className="card p-4">
            <p className="text-sm text-[var(--muted)]">Active</p>
            <p className="text-2xl font-bold text-[var(--success)]">{activeCount}</p>
          </div>
          <div className="card p-4">
            <p className="text-sm text-[var(--muted)]">Suspended</p>
            <p className="text-2xl font-bold text-[var(--danger)]">{suspendedCount}</p>
          </div>
        </div>

        <div className="card overflow-hidden">
          {isLoading && <p className="p-6 text-[var(--muted)]">Loading organizations...</p>}
          {error && (
            <p className="p-6 text-[var(--danger)]">
              {error instanceof Error ? error.message : "Failed to load organizations"}
            </p>
          )}
          {!isLoading && !error && (
            <div className="overflow-x-auto">
              <table>
                <thead>
                  <tr>
                    <th>Organization</th>
                    <th>Status</th>
                    <th>Plan</th>
                    <th>Users</th>
                    <th>Resumes (month)</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {orgs.map((org) => (
                    <OrganizationRow
                      key={org.id}
                      org={org}
                      onSuspend={(id) => suspendMutation.mutate(id)}
                      suspending={suspendMutation.isPending}
                    />
                  ))}
                  {orgs.length === 0 && (
                    <tr>
                      <td colSpan={6} className="text-center text-[var(--muted)]">
                        No organizations registered yet
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </AppShell>
    </AuthGuard>
  );
}
