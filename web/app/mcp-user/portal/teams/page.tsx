'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { Users, Plus, Clock, CheckCircle, XCircle, ShieldCheck } from 'lucide-react'
import { API_BASE } from '@/lib/config'
import UserPortalHeader from '@/components/user-portal-header'

type TeamRequest = {
  id: string; team_name: string; reason: string; status: string
  created_at: string; reviewed_at: string | null; team_id: string | null
}
type AdminTeam = { id: string; name: string } | null

const STATUS_ICON = {
  pending:  <Clock className="w-4 h-4 text-yellow-500" />,
  approved: <CheckCircle className="w-4 h-4 text-green-500" />,
  rejected: <XCircle className="w-4 h-4 text-red-500" />,
}

export default function TeamsPage() {
  const [requests, setRequests] = useState<TeamRequest[]>([])
  const [adminTeam, setAdminTeam] = useState<AdminTeam>(null)
  const [showForm, setShowForm] = useState(false)
  const [teamName, setTeamName] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [loading, setLoading] = useState(true)

  const fetchRequests = useCallback(async () => {
    const res = await fetch(`${API_BASE}/portal/team-requests`)
    if (res.status === 401) { window.location.href = '/panel/mcp-user/login'; return }
    if (res.ok) {
      const data = await res.json()
      setRequests(data.requests ?? [])
      setAdminTeam(data.admin_team ?? null)
    }
    setLoading(false)
  }, [])

  useEffect(() => { fetchRequests() }, [fetchRequests])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    const res = await fetch(`${API_BASE}/portal/team-requests`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ team_name: teamName, reason }),
    })
    const data = await res.json()
    if (!res.ok) { setError(data.error ?? 'Failed'); setSubmitting(false); return }
    setShowForm(false); setTeamName(''); setReason('')
    fetchRequests()
    setSubmitting(false)
  }

  const hasPending = requests.some(r => r.status === 'pending')
  const canRequest = !hasPending && !adminTeam

  return (
    <div className="min-h-screen bg-gray-50">
      <UserPortalHeader title="Teams" subtitle="Manage your team workspaces" accentColor="bg-blue-600" />

      <main className="max-w-3xl mx-auto px-4 py-5 md:px-6 md:py-6 space-y-5">

        {/* Admin team banner */}
        {adminTeam && (
          <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-blue-600 flex-shrink-0" />
              <p className="text-sm text-blue-800">
                You are admin of <span className="font-semibold">{adminTeam.name}</span>. Only one admin team is allowed per user.
              </p>
            </div>
            <Link href={`/mcp-user/teams/${adminTeam.id}`}
              className="flex-shrink-0 text-sm text-blue-600 hover:underline font-medium">
              Manage →
            </Link>
          </div>
        )}

        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900">My Teams</h2>
          {canRequest && (
            <button
              onClick={() => setShowForm(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span className="hidden sm:inline">Request Team</span>
            </button>
          )}
        </div>

        {loading ? (
          <div className="text-center text-sm text-gray-400 py-8">Loading…</div>
        ) : requests.length === 0 ? (
          <div className="bg-white rounded-2xl border border-gray-200 p-10 text-center">
            <Users className="w-8 h-8 text-gray-300 mx-auto mb-3" />
            <p className="text-sm text-gray-500">No team requests yet.</p>
            <p className="text-xs text-gray-400 mt-1">Request a team to collaborate with other users.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {requests.map(r => (
              <div key={r.id} className="bg-white rounded-2xl border border-gray-200 p-4 md:p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    {STATUS_ICON[r.status as keyof typeof STATUS_ICON]}
                    <span className="font-semibold text-gray-900 truncate">{r.team_name}</span>
                    <span className={`flex-shrink-0 text-xs px-2 py-0.5 rounded-full font-medium ${
                      r.status === 'approved' ? 'bg-green-50 text-green-700' :
                      r.status === 'rejected' ? 'bg-red-50 text-red-700' :
                      'bg-yellow-50 text-yellow-700'
                    }`}>{r.status}</span>
                  </div>
                  {r.status === 'approved' && r.team_id && (
                    <Link href={`/mcp-user/teams/${r.team_id}`}
                      className="flex-shrink-0 text-sm text-blue-600 hover:underline font-medium">
                      Manage →
                    </Link>
                  )}
                </div>
                {r.reason && <p className="text-sm text-gray-500 mt-2">{r.reason}</p>}
                <p className="text-xs text-gray-400 mt-2">
                  Requested {new Date(r.created_at).toLocaleDateString()}
                  {r.reviewed_at && ` · Reviewed ${new Date(r.reviewed_at).toLocaleDateString()}`}
                </p>
              </div>
            ))}
          </div>
        )}
      </main>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 p-4">
          <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-md space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">Request a Team</h2>
            {error && <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Team name</label>
              <input type="text" value={teamName} onChange={e => setTeamName(e.target.value)} required autoFocus
                className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="my-team (lowercase, letters, numbers, - _)" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Reason <span className="text-gray-400 font-normal">(optional)</span></label>
              <textarea value={reason} onChange={e => setReason(e.target.value)} rows={3}
                className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                placeholder="Describe what this team is for…" />
            </div>
            <div className="flex gap-3 pt-1">
              <button type="button" onClick={() => setShowForm(false)}
                className="flex-1 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
                Cancel
              </button>
              <button type="submit" disabled={submitting}
                className="flex-1 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white text-sm font-medium rounded-lg transition-colors">
                {submitting ? 'Submitting…' : 'Submit Request'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
