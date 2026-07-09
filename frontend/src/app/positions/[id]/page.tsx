"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ChangeEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import {
  bulkCandidateAction,
  bulkUploadResumes,
  generateCriteria,
  getCriteria,
  getJob,
  getPosition,
  listCandidates,
  sendEmails,
  startScreening,
  updatePosition,
} from "@/lib/api";

function pipelineBadge(status: string) {
  const map: Record<string, string> = {
    new: "badge-muted",
    screening: "badge-accent",
    shortlisted: "badge-success",
    rejected: "badge-danger",
    interview: "badge-warning",
    offer: "badge-accent",
    hired: "badge-success",
  };
  return <span className={`badge ${map[status] || "badge-muted"}`}>{status}</span>;
}

export default function PositionDetailPage() {
  const params = useParams();
  const positionId = params.id as string;
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [uploadError, setUploadError] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobMessage, setJobMessage] = useState("");

  const { data: position, isLoading: loadingPosition } = useQuery({
    queryKey: ["position", positionId],
    queryFn: () => getPosition(positionId),
  });

  const { data: criteria } = useQuery({
    queryKey: ["criteria", positionId],
    queryFn: () => getCriteria(positionId),
  });

  const { data: candidates = [], isLoading: loadingCandidates } = useQuery({
    queryKey: ["candidates", positionId],
    queryFn: () => listCandidates(positionId),
  });

  const uploadMutation = useMutation({
    mutationFn: (files: File[]) => bulkUploadResumes(positionId, files),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["candidates", positionId] });
      setUploadError("");
    },
    onError: (err) => setUploadError(err instanceof Error ? err.message : "Upload failed"),
  });

  const criteriaMutation = useMutation({
    mutationFn: () => generateCriteria(positionId),
    onSuccess: (job) => {
      setJobId(job.id);
      setJobMessage("Generating scoring criteria...");
    },
  });

  const screeningMutation = useMutation({
    mutationFn: () => startScreening(positionId),
    onSuccess: (job) => {
      setJobId(job.id);
      setJobMessage("Screening resumes...");
    },
  });

  const bulkMutation = useMutation({
    mutationFn: ({ ids, action }: { ids: string[]; action: string }) =>
      bulkCandidateAction(ids, action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["candidates", positionId] });
      setSelected(new Set());
    },
  });

  const emailMutation = useMutation({
    mutationFn: ({ ids, template }: { ids: string[]; template: string }) =>
      sendEmails(ids, template),
  });

  const closeMutation = useMutation({
    mutationFn: () => updatePosition(positionId, { status: "closed" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["position", positionId] }),
  });

  useEffect(() => {
    if (!jobId) return;
    const interval = setInterval(async () => {
      try {
        const job = await getJob(jobId);
        setJobMessage(`${job.job_type}: ${job.status} (${job.progress}/${job.total})`);
        if (job.status === "completed" || job.status === "failed") {
          clearInterval(interval);
          setJobId(null);
          queryClient.invalidateQueries({ queryKey: ["candidates", positionId] });
          queryClient.invalidateQueries({ queryKey: ["criteria", positionId] });
        }
      } catch {
        clearInterval(interval);
        setJobId(null);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [jobId, positionId, queryClient]);

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    if (files.length) uploadMutation.mutate(files);
    e.target.value = "";
  }

  const selectedIds = Array.from(selected);

  if (loadingPosition) {
    return (
      <AuthGuard>
        <AppShell>
          <p className="text-[var(--muted)]">Loading...</p>
        </AppShell>
      </AuthGuard>
    );
  }

  if (!position) {
    return (
      <AuthGuard>
        <AppShell>
          <p className="text-[var(--danger)]">Position not found</p>
          <Link href="/positions" className="mt-4 text-[var(--accent-hover)] hover:underline">
            ← Back to positions
          </Link>
        </AppShell>
      </AuthGuard>
    );
  }

  return (
    <AuthGuard>
      <AppShell>
        <Link href="/positions" className="text-sm text-[var(--muted)] hover:text-white">
          ← Back to positions
        </Link>

        <div className="mt-4 mb-8 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white">{position.title}</h1>
            <p className="mt-1 text-[var(--muted)]">
              {[position.designation, position.location].filter(Boolean).join(" · ") || "No details"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {position.status === "open" && (
              <button
                className="btn btn-secondary text-sm"
                onClick={() => closeMutation.mutate()}
                disabled={closeMutation.isPending}
              >
                Close position
              </button>
            )}
            <span className={`badge ${position.status === "open" ? "badge-success" : "badge-muted"}`}>
              {position.status}
            </span>
          </div>
        </div>

        {jobMessage && (
          <div className="card mb-6 p-4 text-sm text-[var(--accent-hover)]">{jobMessage}</div>
        )}

        <div className="mb-8 grid gap-4 lg:grid-cols-2">
          <div className="card p-6">
            <h2 className="mb-4 font-semibold text-white">AI screening</h2>
            <p className="mb-4 text-sm text-[var(--muted)]">{position.job_description.slice(0, 200)}...</p>
            <div className="flex flex-wrap gap-2">
              <button
                className="btn btn-secondary text-sm"
                onClick={() => criteriaMutation.mutate()}
                disabled={criteriaMutation.isPending || !!jobId}
              >
                {criteria ? "Regenerate criteria" : "Generate criteria"}
              </button>
              <button
                className="btn btn-primary text-sm"
                onClick={() => screeningMutation.mutate()}
                disabled={!criteria || screeningMutation.isPending || !!jobId || candidates.length === 0}
              >
                Start screening
              </button>
            </div>
            {criteria && (
              <p className="mt-3 text-xs text-[var(--success)]">
                Criteria ready ({criteria.criteria.length} dimensions, {criteria.total_points} pts)
              </p>
            )}
          </div>

          <div className="card p-6">
            <h2 className="mb-4 font-semibold text-white">Upload resumes</h2>
            <p className="mb-4 text-sm text-[var(--muted)]">PDF files only. Each upload creates a candidate.</p>
            <label className="btn btn-primary cursor-pointer text-sm">
              {uploadMutation.isPending ? "Uploading..." : "Choose PDF files"}
              <input
                type="file"
                accept=".pdf"
                multiple
                className="hidden"
                onChange={handleFileChange}
                disabled={uploadMutation.isPending}
              />
            </label>
            {uploadError && <p className="mt-2 text-sm text-[var(--danger)]">{uploadError}</p>}
          </div>
        </div>

        {selectedIds.length > 0 && (
          <div className="card mb-4 flex flex-wrap items-center gap-2 p-4">
            <span className="text-sm text-[var(--muted)]">{selectedIds.length} selected</span>
            <button
              className="btn btn-secondary text-xs"
              onClick={() => bulkMutation.mutate({ ids: selectedIds, action: "shortlist" })}
            >
              Shortlist
            </button>
            <button
              className="btn btn-secondary text-xs"
              onClick={() => bulkMutation.mutate({ ids: selectedIds, action: "interview" })}
            >
              Move to interview
            </button>
            <button
              className="btn btn-danger text-xs"
              onClick={() => bulkMutation.mutate({ ids: selectedIds, action: "reject" })}
            >
              Reject
            </button>
            <button
              className="btn btn-secondary text-xs"
              onClick={() => emailMutation.mutate({ ids: selectedIds, template: "rejection" })}
            >
              Send rejection email
            </button>
          </div>
        )}

        <div className="card overflow-hidden">
          <div className="border-b border-[var(--border)] px-6 py-4">
            <h2 className="font-semibold text-white">Candidates ({candidates.length})</h2>
          </div>
          {loadingCandidates && <p className="p-6 text-[var(--muted)]">Loading candidates...</p>}
          {!loadingCandidates && (
            <div className="overflow-x-auto">
              <table>
                <thead>
                  <tr>
                    <th>
                      <input
                        type="checkbox"
                        checked={selected.size === candidates.length && candidates.length > 0}
                        onChange={(e) =>
                          setSelected(
                            e.target.checked ? new Set(candidates.map((c) => c.id)) : new Set()
                          )
                        }
                      />
                    </th>
                    <th>Candidate</th>
                    <th>Resume</th>
                    <th>Score</th>
                    <th>Decision</th>
                    <th>Pipeline</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((c) => (
                    <tr key={c.id}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selected.has(c.id)}
                          onChange={() => toggleSelect(c.id)}
                        />
                      </td>
                      <td>
                        <div className="font-medium text-white">
                          {c.full_name || c.email || "Unknown"}
                        </div>
                        {c.email && <div className="text-sm text-[var(--muted)]">{c.email}</div>}
                      </td>
                      <td className="text-sm text-[var(--muted)]">
                        {c.resume?.original_filename || "—"}
                      </td>
                      <td>
                        {c.screening_result ? (
                          <span className="font-semibold">{c.screening_result.total_score}</span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td>
                        {c.screening_result ? (
                          <span
                            className={`badge ${
                              c.screening_result.decision === "shortlist"
                                ? "badge-success"
                                : "badge-danger"
                            }`}
                          >
                            {c.screening_result.decision}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td>{pipelineBadge(c.pipeline_status)}</td>
                    </tr>
                  ))}
                  {candidates.length === 0 && (
                    <tr>
                      <td colSpan={6} className="text-center text-[var(--muted)]">
                        Upload resumes to get started
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
