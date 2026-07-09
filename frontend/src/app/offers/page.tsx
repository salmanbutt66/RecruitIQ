"use client";

import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import {
  createOffer,
  listCandidates,
  listOffers,
  listPositions,
  sendOffer,
  updateOffer,
} from "@/lib/api";

function statusBadge(status: string) {
  const map: Record<string, string> = {
    draft: "badge-muted",
    sent: "badge-accent",
    accepted: "badge-success",
    rejected: "badge-danger",
    withdrawn: "badge-warning",
  };
  return <span className={`badge ${map[status] || "badge-muted"}`}>{status}</span>;
}

export default function OffersPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    position_id: "",
    candidate_id: "",
    amount: "",
    currency: "PKR",
    offer_date: new Date().toISOString().slice(0, 10),
    notes: "",
  });
  const [error, setError] = useState("");

  const { data: allCandidateLabels = {} } = useQuery({
    queryKey: ["all-candidate-labels"],
    queryFn: async () => {
      const allPositions = await listPositions();
      const labels: Record<string, string> = {};
      await Promise.all(
        allPositions.map(async (p) => {
          const cands = await listCandidates(p.id);
          cands.forEach((c) => {
            labels[c.id] = c.full_name || c.email || c.id;
          });
        })
      );
      return labels;
    },
  });

  const { data: offers = [], isLoading } = useQuery({
    queryKey: ["offers"],
    queryFn: listOffers,
    refetchInterval: 5000,
  });

  const { data: positions = [] } = useQuery({
    queryKey: ["positions"],
    queryFn: listPositions,
  });

  const { data: candidates = [] } = useQuery({
    queryKey: ["offer-candidates", form.position_id],
    queryFn: () => listCandidates(form.position_id),
    enabled: !!form.position_id,
  });

  const eligibleCandidates = candidates.filter((c) =>
    ["shortlisted", "interview", "offer"].includes(c.pipeline_status)
  );

  const candidateLabels = useMemo(() => {
    const map: Record<string, string> = { ...allCandidateLabels };
    candidates.forEach((c) => {
      map[c.id] = c.full_name || c.email || c.id;
    });
    return map;
  }, [allCandidateLabels, candidates]);

  const createMutation = useMutation({
    mutationFn: createOffer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["offers"] });
      setShowForm(false);
      setForm({
        position_id: "",
        candidate_id: "",
        amount: "",
        currency: "PKR",
        offer_date: new Date().toISOString().slice(0, 10),
        notes: "",
      });
      setError("");
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Failed to create offer"),
  });

  const sendMutation = useMutation({
    mutationFn: sendOffer,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["offers"] }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateOffer(id, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["offers"] }),
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    createMutation.mutate({
      candidate_id: form.candidate_id,
      amount: parseInt(form.amount, 10),
      currency: form.currency,
      offer_date: new Date(form.offer_date).toISOString(),
      notes: form.notes || undefined,
    });
  }

  return (
    <AuthGuard>
      <AppShell>
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white">Offers</h1>
            <p className="mt-1 text-[var(--muted)]">Create and manage candidate offer letters</p>
          </div>
          <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
            {showForm ? "Cancel" : "New offer"}
          </button>
        </div>

        {showForm && (
          <form onSubmit={handleSubmit} className="card mb-8 space-y-4 p-6">
            <h2 className="font-semibold text-white">Create offer</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm text-[var(--muted)]">Position</label>
                <select
                  className="select"
                  value={form.position_id}
                  onChange={(e) =>
                    setForm({ ...form, position_id: e.target.value, candidate_id: "" })
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
                <label className="mb-1 block text-sm text-[var(--muted)]">Candidate</label>
                <select
                  className="select"
                  value={form.candidate_id}
                  onChange={(e) => setForm({ ...form, candidate_id: e.target.value })}
                  required
                  disabled={!form.position_id}
                >
                  <option value="">Select candidate</option>
                  {eligibleCandidates.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.full_name || c.email || c.id}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm text-[var(--muted)]">Amount</label>
                <input
                  type="number"
                  className="input"
                  value={form.amount}
                  onChange={(e) => setForm({ ...form, amount: e.target.value })}
                  required
                  min={1}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-[var(--muted)]">Currency</label>
                <input
                  className="input"
                  value={form.currency}
                  onChange={(e) => setForm({ ...form, currency: e.target.value })}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-[var(--muted)]">Offer date</label>
                <input
                  type="date"
                  className="input"
                  value={form.offer_date}
                  onChange={(e) => setForm({ ...form, offer_date: e.target.value })}
                  required
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
            {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
            <button type="submit" className="btn btn-primary" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating..." : "Create offer"}
            </button>
          </form>
        )}

        <div className="card overflow-hidden">
          {isLoading && <p className="p-6 text-[var(--muted)]">Loading offers...</p>}
          {!isLoading && (
            <div className="overflow-x-auto">
              <table>
                <thead>
                  <tr>
                    <th>Candidate</th>
                    <th>Amount</th>
                    <th>Offer date</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {offers.map((o) => (
                    <tr key={o.id}>
                      <td className="text-white">
                        {candidateLabels[o.candidate_id] || o.candidate_id.slice(0, 8) + "…"}
                      </td>
                      <td>
                        {o.currency} {o.amount.toLocaleString()}
                      </td>
                      <td className="text-sm text-[var(--muted)]">
                        {new Date(o.offer_date).toLocaleDateString()}
                      </td>
                      <td>{statusBadge(o.status)}</td>
                      <td>
                        <div className="flex flex-wrap gap-2">
                          {o.status === "draft" && (
                            <button
                              className="btn btn-primary text-xs"
                              onClick={() => sendMutation.mutate(o.id)}
                              disabled={sendMutation.isPending}
                            >
                              Send
                            </button>
                          )}
                          {o.status === "sent" && (
                            <>
                              <button
                                className="btn btn-secondary text-xs"
                                onClick={() =>
                                  updateMutation.mutate({ id: o.id, status: "accepted" })
                                }
                              >
                                Mark accepted
                              </button>
                              <button
                                className="btn btn-danger text-xs"
                                onClick={() =>
                                  updateMutation.mutate({ id: o.id, status: "rejected" })
                                }
                              >
                                Mark rejected
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                  {offers.length === 0 && (
                    <tr>
                      <td colSpan={5} className="text-center text-[var(--muted)]">
                        No offers yet
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
