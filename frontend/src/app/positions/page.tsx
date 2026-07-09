"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { createPosition, listPositions } from "@/lib/api";
import type { DesignationTier } from "@/lib/api";

const DESIGNATION_OPTIONS: { value: DesignationTier; label: string }[] = [
  { value: "director", label: "Director" },
  { value: "manager", label: "Manager" },
  { value: "executive", label: "Executive" },
  { value: "intern_trainee", label: "Intern / Trainee" },
];

function statusBadge(status: string) {
  return status === "open" ? (
    <span className="badge badge-success">open</span>
  ) : (
    <span className="badge badge-muted">{status}</span>
  );
}

export default function PositionsPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
  title: "",
  job_description: "",
  designation: "" as DesignationTier | "",
  location: "",
});
  const [error, setError] = useState("");
  
  const { data: positions = [], isLoading } = useQuery({
    queryKey: ["positions"],
    queryFn: listPositions,
  });

  const createMutation = useMutation({
    mutationFn: createPosition,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["positions"] });
      setShowForm(false);
      setForm({ title: "", job_description: "", designation: "", location: "" });
      setError("");
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Failed to create position"),
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!form.designation) {
      setError("Please select a designation");
      return;
    }
    createMutation.mutate({
      title: form.title,
      job_description: form.job_description,
      designation: form.designation,
      location: form.location || undefined,
    });
  }

  return (
    <AuthGuard>
      <AppShell>
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-[var(--foreground)]">Positions</h1>
            <p className="mt-1 text-[var(--muted)]">Manage open roles and candidate pipelines</p>
          </div>
          <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
            {showForm ? "Cancel" : "New position"}
          </button>
        </div>

        {showForm && (
          <form onSubmit={handleSubmit} className="card mb-8 space-y-4 p-6">
            <h2 className="font-semibold text-[var(--foreground)]">Create position</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm text-[var(--muted)]">Title</label>
                <input
                  className="input"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-[var(--muted)]">Designation</label>
                <select
                  className="input"
                  value={form.designation}
                  onChange={(e) => setForm({ ...form, designation: e.target.value as DesignationTier })}
                  required
                >
                  <option value="" disabled>
                    Select designation
                  </option>
                  {DESIGNATION_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm text-[var(--muted)]">Location</label>
                <input
                  className="input"
                  value={form.location}
                  onChange={(e) => setForm({ ...form, location: e.target.value })}
                />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-sm text-[var(--muted)]">Job description</label>
              <textarea
                className="textarea"
                value={form.job_description}
                onChange={(e) => setForm({ ...form, job_description: e.target.value })}
                required
                minLength={20}
              />
            </div>
            {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
            <button type="submit" className="btn btn-primary" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating..." : "Create position"}
            </button>
          </form>
        )}

        <div className="card overflow-hidden">
          {isLoading && <p className="p-6 text-[var(--muted)]">Loading positions...</p>}
          {!isLoading && (
            <div className="overflow-x-auto">
              <table>
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Location</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((p) => (
                    <tr key={p.id}>
                      <td>
                        <div className="font-medium text-[var(--foreground)]">{p.title}</div>
                        {p.designation && (
                          <div className="text-sm text-[var(--muted)]">{p.designation}</div>
                        )}
                      </td>
                      <td className="text-[var(--muted)]">{p.location || "—"}</td>
                      <td>{statusBadge(p.status)}</td>
                      <td className="text-sm text-[var(--muted)]">
                        {new Date(p.created_at).toLocaleDateString()}
                      </td>
                      <td>
                        <Link
                          href={`/positions/${p.id}`}
                          className="text-sm text-[var(--accent-hover)] hover:underline"
                        >
                          View →
                        </Link>
                      </td>
                    </tr>
                  ))}
                  {positions.length === 0 && (
                    <tr>
                      <td colSpan={5} className="text-center text-[var(--muted)]">
                        No positions yet. Create your first role above.
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
