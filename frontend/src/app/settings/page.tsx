"use client";

import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import {
  createCheckout,
  getMe,
  getOrganization,
  getSubscription,
  inviteUser,
  listEmails,
  openBillingPortal,
  updateOrganization,
} from "@/lib/api";

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [orgForm, setOrgForm] = useState({ name: "", resend_from_email: "" });
  const [inviteForm, setInviteForm] = useState({
    email: "",
    full_name: "",
    role: "hr_manager",
    password: "",
  });
  const [orgError, setOrgError] = useState("");
  const [inviteError, setInviteError] = useState("");
  const [inviteSuccess, setInviteSuccess] = useState("");

  const { data: user } = useQuery({ queryKey: ["me"], queryFn: getMe });

  const { data: org } = useQuery({
    queryKey: ["organization"],
    queryFn: getOrganization,
  });

  const { data: subscription } = useQuery({
    queryKey: ["subscription"],
    queryFn: getSubscription,
  });

  const { data: emails = [] } = useQuery({
    queryKey: ["emails"],
    queryFn: listEmails,
  });

  const orgMutation = useMutation({
    mutationFn: updateOrganization,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organization"] });
      setOrgError("");
    },
    onError: (err) => setOrgError(err instanceof Error ? err.message : "Update failed"),
  });

  const inviteMutation = useMutation({
    mutationFn: inviteUser,
    onSuccess: () => {
      setInviteForm({ email: "", full_name: "", role: "hr_manager", password: "" });
      setInviteError("");
      setInviteSuccess("User invited successfully");
    },
    onError: (err) => {
      setInviteSuccess("");
      setInviteError(err instanceof Error ? err.message : "Invite failed");
    },
  });

  const canManage =
    user?.role === "org_admin" || user?.role === "hr_manager";

  function handleOrgSubmit(e: FormEvent) {
    e.preventDefault();
    orgMutation.mutate({
      name: orgForm.name || org?.name,
      resend_from_email: orgForm.resend_from_email || org?.resend_from_email || undefined,
    });
  }

  function handleInviteSubmit(e: FormEvent) {
    e.preventDefault();
    inviteMutation.mutate(inviteForm);
  }

  async function handleUpgrade(plan: string) {
    try {
      const { checkout_url } = await createCheckout(plan);
      window.location.href = checkout_url;
    } catch (err) {
      alert(err instanceof Error ? err.message : "Checkout failed");
    }
  }

  async function handlePortal() {
    try {
      const { checkout_url } = await openBillingPortal();
      window.location.href = checkout_url;
    } catch (err) {
      alert(err instanceof Error ? err.message : "Could not open billing portal");
    }
  }

  return (
    <AuthGuard>
      <AppShell>
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white">Settings</h1>
          <p className="mt-1 text-[var(--muted)]">Organization, team, and billing</p>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <div className="card p-6">
            <h2 className="mb-4 font-semibold text-white">Your profile</h2>
            {user && (
              <dl className="space-y-3 text-sm">
                <div>
                  <dt className="text-[var(--muted)]">Name</dt>
                  <dd className="text-white">{user.full_name}</dd>
                </div>
                <div>
                  <dt className="text-[var(--muted)]">Email</dt>
                  <dd className="text-white">{user.email}</dd>
                </div>
                <div>
                  <dt className="text-[var(--muted)]">Role</dt>
                  <dd>
                    <span className="badge badge-accent">{user.role}</span>
                  </dd>
                </div>
              </dl>
            )}
          </div>

          <div className="card p-6">
            <h2 className="mb-4 font-semibold text-white">Subscription</h2>
            {subscription && (
              <>
                <dl className="mb-4 space-y-3 text-sm">
                  <div>
                    <dt className="text-[var(--muted)]">Plan</dt>
                    <dd>
                      <span className="badge badge-warning">{subscription.plan}</span>
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[var(--muted)]">Status</dt>
                    <dd>
                      <span className="badge badge-success">{subscription.status}</span>
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[var(--muted)]">Resumes used this month</dt>
                    <dd className="text-white">{subscription.resumes_used_this_month}</dd>
                  </div>
                </dl>
                {user?.role === "org_admin" && (
                  <div className="flex flex-wrap gap-2">
                    <button className="btn btn-secondary text-sm" onClick={() => handleUpgrade("professional")}>
                      Upgrade to Professional
                    </button>
                    <button className="btn btn-secondary text-sm" onClick={handlePortal}>
                      Billing portal
                    </button>
                  </div>
                )}
              </>
            )}
          </div>

          {canManage && org && (
            <div className="card p-6">
              <h2 className="mb-4 font-semibold text-white">Organization</h2>
              <form onSubmit={handleOrgSubmit} className="space-y-4">
                <div>
                  <label className="mb-1 block text-sm text-[var(--muted)]">Name</label>
                  <input
                    className="input"
                    defaultValue={org.name}
                    onChange={(e) => setOrgForm({ ...orgForm, name: e.target.value })}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm text-[var(--muted)]">From email (Resend)</label>
                  <input
                    className="input"
                    defaultValue={org.resend_from_email || ""}
                    onChange={(e) => setOrgForm({ ...orgForm, resend_from_email: e.target.value })}
                    placeholder="HR Team <hr@company.com>"
                  />
                </div>
                {orgError && <p className="text-sm text-[var(--danger)]">{orgError}</p>}
                {user?.role === "org_admin" && (
                  <button type="submit" className="btn btn-primary" disabled={orgMutation.isPending}>
                    Save changes
                  </button>
                )}
              </form>
            </div>
          )}

          {canManage && (
            <div className="card p-6">
              <h2 className="mb-4 font-semibold text-white">Invite team member</h2>
              <form onSubmit={handleInviteSubmit} className="space-y-4">
                <div>
                  <label className="mb-1 block text-sm text-[var(--muted)]">Full name</label>
                  <input
                    className="input"
                    value={inviteForm.full_name}
                    onChange={(e) => setInviteForm({ ...inviteForm, full_name: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm text-[var(--muted)]">Email</label>
                  <input
                    type="email"
                    className="input"
                    value={inviteForm.email}
                    onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm text-[var(--muted)]">Role</label>
                  <select
                    className="select"
                    value={inviteForm.role}
                    onChange={(e) => setInviteForm({ ...inviteForm, role: e.target.value })}
                  >
                    <option value="hr_manager">HR Manager</option>
                    <option value="panelist">Panelist</option>
                    <option value="org_admin">Org Admin</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm text-[var(--muted)]">Temporary password</label>
                  <input
                    type="password"
                    className="input"
                    value={inviteForm.password}
                    onChange={(e) => setInviteForm({ ...inviteForm, password: e.target.value })}
                    required
                    minLength={8}
                  />
                </div>
                {inviteError && <p className="text-sm text-[var(--danger)]">{inviteError}</p>}
                {inviteSuccess && <p className="text-sm text-[var(--success)]">{inviteSuccess}</p>}
                <button type="submit" className="btn btn-primary" disabled={inviteMutation.isPending}>
                  Send invite
                </button>
              </form>
            </div>
          )}
        </div>

        <div className="card mt-6 overflow-hidden">
          <div className="border-b border-[var(--border)] px-6 py-4">
            <h2 className="font-semibold text-white">Recent emails</h2>
          </div>
          <div className="overflow-x-auto">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Template</th>
                  <th>Recipient</th>
                  <th>Subject</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {emails.slice(0, 20).map((e) => (
                  <tr key={e.id}>
                    <td className="text-sm text-[var(--muted)]">
                      {new Date(e.created_at).toLocaleString()}
                    </td>
                    <td>
                      <span className="badge badge-muted">{e.template_type}</span>
                    </td>
                    <td className="text-sm">{e.recipient_email}</td>
                    <td className="text-sm text-[var(--muted)]">{e.subject}</td>
                    <td>
                      <span className="badge badge-success">{e.status}</span>
                    </td>
                  </tr>
                ))}
                {emails.length === 0 && (
                  <tr>
                    <td colSpan={5} className="text-center text-[var(--muted)]">
                      No emails sent yet
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </AppShell>
    </AuthGuard>
  );
}
