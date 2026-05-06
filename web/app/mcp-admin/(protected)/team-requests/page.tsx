'use client'

import { useState, useEffect, useCallback } from 'react'
import { Clock, CheckCircle, XCircle } from 'lucide-react'

import { API_BASE } from '@/lib/config'

type TeamRequest = {
  id: string; team_name: string; reason: string; status: string
  requester_username: string; requester_email: string
  created_at: string; reviewed_at: string | null
}

export default function TeamRequestsPage() {
  const [requests, setRequests] = useState<TeamRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState<string | null>(null)

  const fetchRequests = useCallback(async () => {
    const res = await fetch(`${API_BASE}/admin/team-requests`)
    if (res.ok) setRequests(await res.json())
    setLoading(false)
  }, [])

  useEffect(() => { fetchRequests() }, [fetchRequests])

  async function handleAction(id: string, action: 'approve' | 'reject') {
    if (!confirm(`${action === 'approve' ? 'Approve' : 'Reject'} this team request?`)) return
    setProcessing(id)
    const res = await fetch(`${API_BASE}/admin/team-requests/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action }),
    })
    if (res.ok) fetchRequests()
    setProcessing(null)
  }

  const pending = requests.filter(r => r.status === 'pending')
  const reviewed = requests.filter(r => r.status !== 'pending')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Team Requests</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          {pending.length} pending · {reviewed.length} reviewed
        </p>
      </div>

      {loading ? (
        <div className="p-8 text-center text-sm text-gray-400">Loading…</div>
      ) : requests.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center">
          <p className="text-sm text-gray-400">No team requests yet.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {[...pending, ...reviewed].map(r => (
            <div key={r.id} className="bg-white rounded-2xl border border-gray-200 p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    {r.status === 'pending'  && <Clock className="w-4 h-4 text-yellow-500 flex-shrink-0" />}
                    {r.status === 'approved' && <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />}
                    {r.status === 'rejected' && <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />}
                    <span className="font-semibold text-gray-900">{r.team_name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      r.status === 'approved' ? 'bg-green-50 text-green-700' :
                      r.status === 'rejected' ? 'bg-red-50 text-red-700' :
                      'bg-yellow-50 text-yellow-700'
                    }`}>{r.status}</span>
                  </div>
                  <p className="text-sm text-gray-600 mt-1">
                    <span className="font-medium">{r.requester_username}</span>
                    {' '}
                    <span className="text-gray-400">({r.requester_email})</span>
                  </p>
                  {r.reason && <p className="text-sm text-gray-500 mt-1.5 italic">"{r.reason}"</p>}
                  <p className="text-xs text-gray-400 mt-2">
                    Requested {new Date(r.created_at).toLocaleDateString()}
                    {r.reviewed_at && ` · Reviewed ${new Date(r.reviewed_at).toLocaleDateString()}`}
                  </p>
                </div>
                {r.status === 'pending' && (
                  <div className="flex gap-2 flex-shrink-0">
                    <button
                      disabled={processing === r.id}
                      onClick={() => handleAction(r.id, 'reject')}
                      className="px-3 py-1.5 text-sm font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50"
                    >
                      Reject
                    </button>
                    <button
                      disabled={processing === r.id}
                      onClick={() => handleAction(r.id, 'approve')}
                      className="px-3 py-1.5 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors disabled:opacity-50"
                    >
                      {processing === r.id ? 'Processing…' : 'Approve'}
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
