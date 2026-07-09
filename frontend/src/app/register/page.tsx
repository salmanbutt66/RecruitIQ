"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { register, setTokens } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    email: "",
    password: "",
    full_name: "",
    organization_name: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function update(field: keyof typeof form, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const tokens = await register(form);
      setTokens(tokens.access_token, tokens.refresh_token);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-8">
      <div className="card w-full max-w-md p-8">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-[var(--foreground)]">
            Create your <span className="text-[var(--accent)]">RecruitIQ</span> account
          </h1>
          <p className="mt-2 text-sm text-[var(--muted)]">Start hiring with AI-powered screening</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--muted)]">
              Organization name
            </label>
            <input
              className="input"
              value={form.organization_name}
              onChange={(e) => update("organization_name", e.target.value)}
              required
              minLength={2}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--muted)]">Your name</label>
            <input
              className="input"
              value={form.full_name}
              onChange={(e) => update("full_name", e.target.value)}
              required
              minLength={2}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--muted)]">Work email</label>
            <input
              type="email"
              className="input"
              value={form.email}
              onChange={(e) => update("email", e.target.value)}
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--muted)]">Password</label>
            <input
              type="password"
              className="input"
              value={form.password}
              onChange={(e) => update("password", e.target.value)}
              required
              minLength={8}
            />
          </div>

          {error && (
            <p className="rounded-lg bg-[rgba(239,68,68,0.15)] px-3 py-2 text-sm text-[var(--danger)]">
              {error}
            </p>
          )}

          <button type="submit" className="btn btn-primary w-full" disabled={loading}>
            {loading ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-[var(--muted)]">
          Already have an account?{" "}
          <Link href="/login" className="text-[var(--accent-hover)] hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
