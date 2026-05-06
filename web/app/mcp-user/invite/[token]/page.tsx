'use client'

import { useState, useEffect, use } from 'react'
import { useRouter } from 'next/navigation'
import { Users, CheckCircle, XCircle, Loader2 } from 'lucide-react'
import { API_BASE } from '@/lib/config'

type InviteInfo = {
  team_id: string
  team_name: string
  expires_at: string
  already_member: boolean
}

type State = 'loading' | 'ready' | 'already' | 'joining' | 'joined' | 'error'

export default function InvitePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params)
  const router = useRouter()
  const [state, setState] = useState<State>('loading')
  const [invite, setInvite] = useState<InviteInfo | null>(null)
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    fetch(`${API_BASE}/invite/${token}`)
      .then(async res => {
        if (res.status === 401) {
          // Not logged in — redirect to login with ?next= so we come back here
          window.location.href = `/panel/mcp-user/login?next=/mcp-user/invite/${token}`
          return
        }
        const data = await res.json()
        if (!res.ok) { setErrorMsg(data.error ?? 'Invalid invite'); setState('error'); return }
        if (data.already_member) { setState('already'); setInvite(data); return }
        setInvite(data)
        setState('ready')
      })
      .catch(() => { setErrorMsg('Network error'); setState('error') })
  }, [token])

  async function handleJoin() {
    setState('joining')
    const res = await fetch(`${API_BASE}/invite/${token}`, { method: 'POST' })
    const data = await res.json()
    if (!res.ok) { setErrorMsg(data.error ?? 'Failed to join'); setState('error'); return }
    setState('joined')
    setTimeout(() => router.push(`/mcp-user/teams/${data.team_id}`), 1500)
  }

  if (state === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
      </div>
    )
  }

  if (state === 'error') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-8 max-w-sm w-full text-center space-y-4">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-red-50 mx-auto">
            <XCircle className="w-6 h-6 text-red-500" />
          </div>
          <h1 className="text-lg font-semibold text-gray-900">Invite Invalid</h1>
          <p className="text-sm text-gray-500">{errorMsg}</p>
          <a href="/panel/mcp-user/portal"
            className="inline-block w-full py-2.5 text-sm font-medium text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50 transition-colors">
            Go to Portal
          </a>
        </div>
      </div>
    )
  }

  if (state === 'already') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-8 max-w-sm w-full text-center space-y-4">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-blue-50 mx-auto">
            <Users className="w-6 h-6 text-blue-500" />
          </div>
          <h1 className="text-lg font-semibold text-gray-900">Already a member</h1>
          <p className="text-sm text-gray-500">You are already a member of <strong>{invite?.team_name}</strong>.</p>
          <a href={`/panel/mcp-user/teams/${invite?.team_id}`}
            className="inline-block w-full py-2.5 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
            Go to Team
          </a>
        </div>
      </div>
    )
  }

  if (state === 'joined') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-8 max-w-sm w-full text-center space-y-4">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-green-50 mx-auto">
            <CheckCircle className="w-6 h-6 text-green-500" />
          </div>
          <h1 className="text-lg font-semibold text-gray-900">Joined!</h1>
          <p className="text-sm text-gray-500">Welcome to <strong>{invite?.team_name}</strong>. Redirecting…</p>
        </div>
      </div>
    )
  }

  // state === 'ready'
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-8 max-w-sm w-full space-y-6">
        <div className="text-center space-y-3">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-blue-600 mx-auto">
            <Users className="w-7 h-7 text-white" />
          </div>
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wider font-semibold mb-1">Team Invite</p>
            <h1 className="text-xl font-bold text-gray-900">{invite?.team_name}</h1>
            <p className="text-sm text-gray-500 mt-1">You have been invited to join this team.</p>
          </div>
        </div>

        <div className="bg-gray-50 rounded-xl px-4 py-3 text-xs text-gray-500 text-center">
          Expires {new Date(invite!.expires_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}
        </div>

        <div className="flex flex-col gap-2">
          <button onClick={handleJoin} disabled={state === 'joining'}
            className="w-full py-2.5 text-sm font-medium bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white rounded-lg transition-colors">
            {state === 'joining' ? 'Joining…' : `Join ${invite?.team_name}`}
          </button>
          <a href="/panel/mcp-user/portal"
            className="w-full py-2.5 text-sm font-medium text-center text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors block">
            Cancel
          </a>
        </div>
      </div>
    </div>
  )
}
