export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export type DesignationTier = "director" | "manager" | "executive" | "intern_trainee";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem("access_token", access);
  localStorage.setItem("refresh_token", refresh);
}

export function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

function parseErrorDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || String(d)).join(", ");
  return "Request failed";
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (res.status === 401) {
    clearTokens();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(parseErrorDetail(err.detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// Types
export type User = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  organization_id: string;
  is_active: boolean;
};

export type Organization = {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  resend_from_email: string | null;
};

export type DashboardStats = {
  open_positions: number;
  total_candidates: number;
  shortlisted: number;
  rejected: number;
  in_interview: number;
  offers_pending: number;
};

export type Position = {
  id: string;
  organization_id: string;
  title: string;
  job_description: string;
  status: string;
  designation: DesignationTier | null;
  location: string | null;
  created_at: string;
};

export type ScoringCriteria = {
  id: string;
  position_id: string;
  jd_analysis: Record<string, unknown>;
  criteria: Array<Record<string, unknown>>;
  total_points: number;
  generated_by_model: string | null;
};

export type Candidate = {
  id: string;
  organization_id: string;
  position_id: string;
  full_name: string | null;
  email: string | null;
  phone: string | null;
  location: string | null;
  designation: string | null;
  pipeline_status: string;
  created_at: string;
};

export type Resume = {
  id: string;
  candidate_id: string;
  original_filename: string;
  file_size_bytes: number;
  storage_key: string;
  created_at: string;
};

export type ScreeningResult = {
  id: string;
  candidate_id: string;
  position_id: string;
  total_score: number;
  breakdown: Array<Record<string, unknown>>;
  decision: string;
  summary: string;
  reason: string;
  reviewed_by_openai: boolean;
  created_at: string;
};

export type CandidateWithScreening = Candidate & {
  screening_result: ScreeningResult | null;
  resume: Resume | null;
};

export type InterviewBatch = {
  id: string;
  organization_id: string;
  position_id: string;
  name: string;
  scheduled_at: string | null;
  location: string | null;
  notes: string | null;
  candidate_order: string[];
  created_at: string;
};

export type Offer = {
  id: string;
  candidate_id: string;
  amount: number;
  currency: string;
  offer_date: string;
  joining_date: string | null;
  status: string;
  notes: string | null;
  status_history: Array<Record<string, unknown>>;
  created_at: string;
};

export type Subscription = {
  plan: string;
  status: string;
  resumes_used_this_month: number;
  usage_period_start: string | null;
};

export type BackgroundJob = {
  id: string;
  job_type: string;
  status: string;
  progress: number;
  total: number;
  payload: Record<string, unknown>;
  result: Record<string, unknown>;
  error: string | null;
  created_at: string;
};

export type EmailLog = {
  id: string;
  template_type: string;
  recipient_email: string;
  subject: string;
  status: string;
  created_at: string;
};

// Auth
export async function login(email: string, password: string) {
  return apiFetch<{ access_token: string; refresh_token: string }>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function register(data: {
  email: string;
  password: string;
  full_name: string;
  organization_name: string;
}) {
  return apiFetch<{ access_token: string; refresh_token: string }>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getMe() {
  return apiFetch<User>("/api/v1/auth/me");
}

export async function inviteUser(data: {
  email: string;
  full_name: string;
  role: string;
  password: string;
}) {
  return apiFetch<User>("/api/v1/auth/invite", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// Organization
export async function getOrganization() {
  return apiFetch<Organization>("/api/v1/organizations/me");
}

export async function updateOrganization(data: { name?: string; resend_from_email?: string }) {
  return apiFetch<Organization>("/api/v1/organizations/me", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function getDashboardStats() {
  return apiFetch<DashboardStats>("/api/v1/dashboard/stats");
}

// Positions
export async function listPositions() {
  return apiFetch<Position[]>("/api/v1/positions");
}

export async function createPosition(data: {
  title: string;
  job_description: string;
  designation: DesignationTier;
  location?: string;
}) {
  return apiFetch<Position>("/api/v1/positions", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getPosition(id: string) {
  return apiFetch<Position>(`/api/v1/positions/${id}`);
}

export async function updatePosition(id: string, data: Partial<Position>) {
  return apiFetch<Position>(`/api/v1/positions/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function getCriteria(positionId: string) {
  return apiFetch<ScoringCriteria | null>(`/api/v1/positions/${positionId}/criteria`);
}

export async function generateCriteria(positionId: string) {
  return apiFetch<BackgroundJob>(`/api/v1/positions/${positionId}/generate-criteria`, {
    method: "POST",
  });
}

// Candidates & resumes
export async function listCandidates(positionId: string, params?: { pipeline_status?: string }) {
  const qs = params?.pipeline_status ? `?pipeline_status=${params.pipeline_status}` : "";
  return apiFetch<CandidateWithScreening[]>(`/api/v1/positions/${positionId}/candidates${qs}`);
}

export async function bulkUploadResumes(positionId: string, files: File[]) {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  return apiFetch<Resume[]>(`/api/v1/positions/${positionId}/resumes/bulk`, {
    method: "POST",
    body: form,
  });
}

export async function bulkCandidateAction(candidateIds: string[], action: string) {
  return apiFetch<{ updated: number }>("/api/v1/candidates/bulk-action", {
    method: "POST",
    body: JSON.stringify({ candidate_ids: candidateIds, action }),
  });
}

export async function startScreening(positionId: string, resumeIds?: string[]) {
  return apiFetch<BackgroundJob>("/api/v1/screening/start", {
    method: "POST",
    body: JSON.stringify({ position_id: positionId, resume_ids: resumeIds }),
  });
}

export async function getJob(jobId: string) {
  return apiFetch<BackgroundJob>(`/api/v1/jobs/${jobId}`);
}

// Interviews
export async function listInterviewBatches() {
  return apiFetch<InterviewBatch[]>("/api/v1/interview-batches");
}

export async function createInterviewBatch(data: {
  position_id: string;
  name: string;
  scheduled_at?: string;
  location?: string;
  notes?: string;
  candidate_ids: string[];
  panelist_ids: string[];
}) {
  return apiFetch<InterviewBatch>("/api/v1/interview-batches", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// Offers
export async function listOffers() {
  return apiFetch<Offer[]>("/api/v1/offers");
}

export async function createOffer(data: {
  candidate_id: string;
  amount: number;
  currency?: string;
  offer_date: string;
  notes?: string;
}) {
  return apiFetch<Offer>("/api/v1/offers", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateOffer(id: string, data: { status?: string; amount?: number; notes?: string }) {
  return apiFetch<Offer>(`/api/v1/offers/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function sendOffer(id: string) {
  return apiFetch<{ status: string }>(`/api/v1/offers/${id}/send`, { method: "POST" });
}

// Billing
export async function getSubscription() {
  return apiFetch<Subscription>("/api/v1/billing/subscription");
}

export async function createCheckout(plan: string) {
  return apiFetch<{ checkout_url: string }>(`/api/v1/billing/checkout/${plan}`, { method: "POST" });
}

export async function openBillingPortal() {
  return apiFetch<{ checkout_url: string }>("/api/v1/billing/portal", { method: "POST" });
}

// Emails
export async function listEmails() {
  return apiFetch<EmailLog[]>("/api/v1/emails");
}

export async function sendEmails(candidateIds: string[], templateType: string) {
  return apiFetch<{ sent: number }>("/api/v1/emails/send", {
    method: "POST",
    body: JSON.stringify({ candidate_ids: candidateIds, template_type: templateType }),
  });
}
