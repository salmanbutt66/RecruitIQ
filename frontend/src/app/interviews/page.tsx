"use client";

import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import {
  createInterviewBatch,
  listCandidates,
  listInterviewBatches,
  listPositions,
} from "@/lib/api";

export default function InterviewsPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    position_id: "",
    name: "",
    scheduled_at: "",
    location: "",
    notes: "",
    candidate_ids: [] as string[],
  });
  const [error, setError] = useState("");

  const { data: batches = [], isLoading } = useQuery({
    queryKey: ["interview-batches"],
    queryFn: listInterviewBatches,
  });

  const { data: positions = [] } = useQuery({
    queryKey: ["positions"],
    queryFn: listPositions,
  });

  const { data: candidates = [] } = useQuery({
    queryKey: ["interview-candidates", form.position_id],
    queryFn: () => listCandidates(form.position_id),
    enabled: !!form.position_id,
  });

  const eligibleCandidates = candidates.filter((c) =>
    ["shortlisted", "interview"].includes(c.pipeline_status)
  );

  const positionMap = Object.fromEntries(positions.map((p) => [p.id, p.title]));

  const createMutation = useMutation({
    mutationFn: createInterviewBatch,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["interview-batches"] });
      setShowForm(false);
      setForm({
        position_id: "",
        name: "",
        scheduled_at: "",
        location: "",
        notes: "",
        candidate_ids: [],
      });
      setError("");
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Failed to create batch"),
  });

  function toggleCandidate(id: string) {
    setForm((prev) => ({
      ...prev,
      candidate_ids: prev.candidate_ids.includes(id)
        ? prev.candidate_ids.filter((c) => c !== id)
        : [...prev.candidate_ids, id],
    }));
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (form.candidate_ids.length === 0) {
      setError("Select at least one candidate");
      return;
    }
    createMutation.mutate({
      position_id: form.position_id,
      name: form.name,
      scheduled_at: form.scheduled_at ? new Date(form.scheduled_at).toISOString() : undefined,
      location: form.location || undefined,
      notes: form.notes || undefined,
      candidate_ids: form.candidate_ids,
      panelist_ids: [],
    });
  }

  return (
    <AuthGuard>
      <AppShell>
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white">Interviews</h1>
            <p className="mt-1 text-[var(--muted)]">Schedule and manage interview batches</p>
          </div>
          <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
            {showForm ? "Cancel" : "New batch"}
          </button>
        </div>

        {showForm && (
          <form onSubmit={handleSubmit} className="card mb-8 space-y-4 p-6">
            <h2 className="font-semibold text-white">Create interview batch</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm text-[var(--muted)]">Position</label>
                <select
                  className="select"
                  value={form.position_id}
                  onChange={(e) =>
                    setForm({ ...form, position_id: e.target.value, candidate_ids: [] })
                  }
                  required
                >
                  <option value="">Select position</option>
                  {positions.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.title}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm text-[var(--muted)]">Batch name</label>
                <input
                  className="input"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  required
                  placeholder="e.g. Round 1 — Engineering"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-[var(--muted)]">Scheduled date</label>
                <input
                  type="datetime-local"
                  className="input"
                  value={form.scheduled_at}
                  onChange={(e) => setForm({ ...form, scheduled_at: e.target.value })}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-[var(--muted)]">Location</label>
                <input
                  className="input"
                  value={form.location}
                  onChange={(e) => setForm({ ...form, location: e.target.value })}
                  placeholder="Office / Zoom link"
                />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-sm text-[var(--muted)]">Notes</label>
              <textarea
                className="textarea"
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                rows={3}
              />
            </div>

            {form.position_id && (
              <div>
                <label className="mb-2 block text-sm text-[var(--muted)]">
                  Candidates (shortlisted or in interview)
                </label>
                {eligibleCandidates.length === 0 ? (
                  <p className="text-sm text-[var(--muted)]">
                    No eligible candidates. Shortlist candidates from the position page first.
                  </p>
                ) : (
                  <div className="space-y-2 rounded-lg border border-[var(--border)] p-4">
                    {eligibleCandidates.map((c) => (
                      <label key={c.id} className="flex items-center gap-3 text-sm">
                        <input
                          type="checkbox"
                          checked={form.candidate_ids.includes(c.id)}
                          onChange={() => toggleCandidate(c.id)}
                        />
                        <span>{c.full_name || c.email || c.id}</span>
                        <span className="badge badge-muted">{c.pipeline_status}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}

            {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
            <button type="submit" className="btn btn-primary" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating..." : "Create batch"}
            </button>
          </form>
        )}

        <div className="card overflow-hidden">
          {isLoading && <p className="p-6 text-[var(--muted)]">Loading batches...</p>}
          {!isLoading && (
            <div className="overflow-x-auto">
              <table>
                <thead>
                  <tr>
                    <th>Batch</th>
                    <th>Position</th>
                    <th>Scheduled</th>
                    <th>Location</th>
                    <th>Candidates</th>
                  </tr>
                </thead>
                <tbody>
                  {batches.map((b) => (
                    <tr key={b.id}>
                      <td>
                        <div className="font-medium text-white">{b.name}</div>
                        {b.notes && <div className="text-sm text-[var(--muted)]">{b.notes}</div>}
                      </td>
                      <td className="text-[var(--muted)]">
                        {positionMap[b.position_id] || b.position_id}
                      </td>
                      <td className="text-sm text-[var(--muted)]">
                        {b.scheduled_at
                          ? new Date(b.scheduled_at).toLocaleString()
                          : "Not scheduled"}
                      </td>
                      <td className="text-[var(--muted)]">{b.location || "—"}</td>
                      <td>
                        <span className="badge badge-accent">{b.candidate_order.length}</span>
                      </td>
                    </tr>
                  ))}
                  {batches.length === 0 && (
                    <tr>
                      <td colSpan={5} className="text-center text-[var(--muted)]">
                        No interview batches yet
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
