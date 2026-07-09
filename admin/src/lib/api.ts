export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
    const detail = err.detail;
    throw new Error(typeof detail === "string" ? detail : "Request failed");
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export type User = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  organization_id: string;
  is_active: boolean;
};

export type AdminOrganization = {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  resend_from_email: string | null;
  user_count: number;
  subscription_plan: string | null;
  resumes_used: number;
};

export type AuditLog = {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  details: Record<string, unknown>;
  created_at: string;
  user_id: string | null;
};

export async function login(email: string, password: string) {
  return apiFetch<{ access_token: string; refresh_token: string }>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function getMe() {
  return apiFetch<User>("/api/v1/auth/me");
}

export async function listOrganizations() {
  return apiFetch<AdminOrganization[]>("/api/v1/admin/organizations");
}

export async function suspendOrganization(orgId: string) {
  return apiFetch<{ status: string }>(`/api/v1/admin/organizations/${orgId}/suspend`, {
    method: "PATCH",
  });
}

export async function listAuditLogs() {
  return apiFetch<AuditLog[]>("/api/v1/admin/audit-logs");
}
