"use client";

import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { listAuditLogs } from "@/lib/api";

function formatDate(iso: string) {
  return new Date(iso).toLocaleString();
}

export default function AuditLogsPage() {
  const { data: logs = [], isLoading, error } = useQuery({
    queryKey: ["admin-audit-logs"],
    queryFn: listAuditLogs,
  });

  return (
    <AuthGuard>
      <AppShell>
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white">Audit Logs</h1>
          <p className="mt-1 text-[var(--muted)]">Recent platform activity (last 200 events)</p>
        </div>

        <div className="card overflow-hidden">
          {isLoading && <p className="p-6 text-[var(--muted)]">Loading audit logs...</p>}
          {error && (
            <p className="p-6 text-[var(--danger)]">
              {error instanceof Error ? error.message : "Failed to load audit logs"}
            </p>
          )}
          {!isLoading && !error && (
            <div className="overflow-x-auto">
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Action</th>
                    <th>Entity</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => (
                    <tr key={log.id}>
                      <td className="whitespace-nowrap text-sm text-[var(--muted)]">
                        {formatDate(log.created_at)}
                      </td>
                      <td>
                        <span className="badge badge-muted">{log.action}</span>
                      </td>
                      <td>
                        <div className="text-sm">{log.entity_type}</div>
                        {log.entity_id && (
                          <div className="text-xs text-[var(--muted)]">{log.entity_id}</div>
                        )}
                      </td>
                      <td>
                        {Object.keys(log.details).length > 0 ? (
                          <code className="text-xs text-[var(--muted)]">
                            {JSON.stringify(log.details)}
                          </code>
                        ) : (
                          <span className="text-[var(--muted)]">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {logs.length === 0 && (
                    <tr>
                      <td colSpan={4} className="text-center text-[var(--muted)]">
                        No audit logs yet
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
