'use client'

import { useState, useEffect, useCallback, use } from 'react'
import { Users, Key, BookOpen, MessageSquare, Trash2, Plus, Copy, Check } from 'lucide-react'

type Tab = 'sessions' | 'members' | 'tokens' | 'skills'
type Member = { id: string; username: string; email: string; role: string; joined_at: string }
type Token  = { id: string; name: string; revoked: boolean; created_at: string }
type Session = { session_id: string; title: string; notes_count: number; updated_at: string }
type Skill   = { slug: string; name: string; summary: string }

export default function TeamAdminPage({ params }: { params: Promise<{ teamId: string }> }) {
  const { teamId } = use(params)
  const [tab, setTab] = useState<Tab>('sessions')
  const [teamName, setTeamName] = useState('')
  const [role, setRole] = useState('')
  const [members, setMembers] = useState<Member[]>([])
  const [tokens, setTokens] = useState<Token[]>([])
  const [sessions, setSessions] = useState<Session[]>([])
  const [skills, setSkills] = useState<Skill[]>([])
  const [newToken, setNewToken] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [addUsername, setAddUsername] = useState('')
  const [addSkugSlug, setAddSkillSlug] = useState('')
  const [error, setError] = useState('')

  const API = `/panel/api/teams/${teamId}`

  const fetchTeam = useCallback(async () => {
    const res = await fetch(API)
    if (res.ok) { const d = await res.json(); setTeamName(d.name); setRole(d.role) }
  }, [API])

  const fetchMembers = useCallback(async () => {
    const res = await fetch(`${API}/members`)
    if (res.ok) setMembers(await res.json())
  }, [API])

  const fetchTokens = useCallback(async () => {
    const res = await fetch(`${API}/tokens`)
    if (res.ok) setTokens(await res.json())
  }, [API])

  const fetchSessions = useCallback(async () => {
    const res = await fetch(`${API}/sessions`)
    if (res.ok) setSessions(await res.json())
  }, [API])

  const fetchSkills = useCallback(async () => {
    const res = await fetch(`${API}/skills`)
    if (res.ok) setSkills(await res.json())
  }, [API])

  useEffect(() => {
    fetchTeam()
    fetchSessions(); fetchMembers(); fetchTokens(); fetchSkills()
  }, [fetchTeam, fetchSessions, fetchMembers, fetchTokens, fetchSkills])

  async function createToken() {
    const name = prompt('Token name:')
    if (!name) return
    const res = await fetch(`${API}/tokens`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) })
    const data = await res.json()
    if (res.ok) { setNewToken(data.token); fetchTokens() }
  }

  async function revokeToken(id: string) {
    if (!confirm('Revoke this token?')) return
    await fetch(`${API}/tokens/${id}`, { method: 'DELETE' })
    fetchTokens()
  }

  async function addMember(e: React.FormEvent) {
    e.preventDefault(); setError('')
    const res = await fetch(`${API}/members`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: addUsername }) })
    const data = await res.json()
    if (!res.ok) { setError(data.error ?? 'Failed'); return }
    setAddUsername(''); fetchMembers()
  }

  async function removeMember(userId: string) {
    if (!confirm('Remove this member?')) return
    await fetch(`${API}/members/${userId}`, { method: 'DELETE' })
    fetchMembers()
  }

  async function addSkill(e: React.FormEvent) {
    e.preventDefault(); setError('')
    const res = await fetch(`${API}/skills`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ slug: addSkugSlug }) })
    const data = await res.json()
    if (!res.ok) { setError(data.error ?? 'Failed'); return }
    setAddSkillSlug(''); fetchSkills()
  }

  async function removeSkill(slug: string) {
    if (!confirm('Remove skill from team?')) return
    await fetch(`${API}/skills/${slug}`, { method: 'DELETE' })
    fetchSkills()
  }

  async function deleteSession(id: string) {
    if (!confirm('Delete this session?')) return
    await fetch(`${API}/sessions/${id}`, { method: 'DELETE' })
    fetchSessions()
  }

  async function copyToken(t: string) {
    await navigator.clipboard.writeText(t)
    setCopied(true); setTimeout(() => setCopied(false), 2000)
  }

  const isAdmin = role === 'admin'
  const TABS: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: 'sessions', label: 'Sessions', icon: <MessageSquare className="w-4 h-4" /> },
    { key: 'members',  label: 'Members',  icon: <Users className="w-4 h-4" /> },
    { key: 'tokens',   label: 'Tokens',   icon: <Key className="w-4 h-4" /> },
    { key: 'skills',   label: 'Skills',   icon: <BookOpen className="w-4 h-4" /> },
  ]

  return (
    <div className="max-w-4xl mx-auto space-y-5 p-4">
      <div>
        <p className="text-xs text-gray-400 uppercase tracking-wider font-semibold">Team</p>
        <h1 className="text-2xl font-bold text-gray-900">{teamName || '…'}</h1>
        <p className="text-sm text-gray-500 capitalize">Your role: {role}</p>
      </div>

      {newToken && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-2">
          <p className="text-sm font-semibold text-amber-800">⚠️ Copy this token now — it will not be shown again</p>
          <div className="flex gap-2">
            <code className="flex-1 bg-gray-900 text-green-400 px-3 py-2 rounded-lg text-xs font-mono break-all">{newToken}</code>
            <button onClick={() => copyToken(newToken)} className="p-2 rounded-lg border hover:bg-gray-50">
              {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4 text-gray-500" />}
            </button>
          </div>
          <button onClick={() => setNewToken(null)} className="text-xs text-amber-700 hover:underline">Dismiss</button>
        </div>
      )}

      {error && <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>}

      <div className="flex gap-1 border-b border-gray-200">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${tab === t.key ? 'border-blue-600 text-blue-700' : 'border-transparent text-gray-500 hover:text-gray-900'}`}>
            {t.icon}{t.label}
          </button>
        ))}
      </div>

      {tab === 'sessions' && (
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
          {sessions.length === 0 ? (
            <div className="p-8 text-center text-sm text-gray-400">No team sessions yet.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Session ID</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Title</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Notes</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Updated</th>
                  {isAdmin && <th className="px-4 py-3" />}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {sessions.map(s => (
                  <tr key={s.session_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">{s.session_id}</td>
                    <td className="px-4 py-3 text-gray-900 font-medium">{s.title}</td>
                    <td className="px-4 py-3 text-gray-500">{s.notes_count}</td>
                    <td className="px-4 py-3 text-gray-400 text-xs">{new Date(s.updated_at).toLocaleDateString()}</td>
                    {isAdmin && (
                      <td className="px-4 py-3 text-right">
                        <button onClick={() => deleteSession(s.session_id)} className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === 'members' && (
        <div className="space-y-4">
          {isAdmin && (
            <form onSubmit={addMember} className="flex gap-2">
              <input type="text" value={addUsername} onChange={e => setAddUsername(e.target.value)} required
                placeholder="Add member by username"
                className="flex-1 px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <button type="submit" className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors">
                <Plus className="w-4 h-4" /> Add
              </button>
            </form>
          )}
          <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Username</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Email</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Role</th>
                  {isAdmin && <th className="px-4 py-3" />}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {members.map(m => (
                  <tr key={m.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">{m.username}</td>
                    <td className="px-4 py-3 text-gray-500">{m.email}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${m.role === 'admin' ? 'bg-blue-50 text-blue-700' : 'bg-gray-100 text-gray-600'}`}>{m.role}</span>
                    </td>
                    {isAdmin && (
                      <td className="px-4 py-3 text-right">
                        <button onClick={() => removeMember(m.id)} className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'tokens' && (
        <div className="space-y-4">
          {isAdmin && (
            <button onClick={createToken} className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors">
              <Plus className="w-4 h-4" /> New Token
            </button>
          )}
          <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
            {tokens.length === 0 ? (
              <div className="p-8 text-center text-sm text-gray-400">No tokens yet.</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Name</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Status</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Created</th>
                    {isAdmin && <th className="px-4 py-3" />}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {tokens.map(t => (
                    <tr key={t.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-gray-900">{t.name}</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${t.revoked ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
                          {t.revoked ? 'revoked' : 'active'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-400 text-xs">{new Date(t.created_at).toLocaleDateString()}</td>
                      {isAdmin && !t.revoked && (
                        <td className="px-4 py-3 text-right">
                          <button onClick={() => revokeToken(t.id)} className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {tab === 'skills' && (
        <div className="space-y-4">
          {isAdmin && (
            <form onSubmit={addSkill} className="flex gap-2">
              <input type="text" value={addSkugSlug} onChange={e => setAddSkillSlug(e.target.value)} required
                placeholder="Skill slug (e.g. python)"
                className="flex-1 px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <button type="submit" className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors">
                <Plus className="w-4 h-4" /> Add
              </button>
            </form>
          )}
          <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
            {skills.length === 0 ? (
              <div className="p-8 text-center text-sm text-gray-400">No skills added to this team yet.</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Skill</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Summary</th>
                    {isAdmin && <th className="px-4 py-3" />}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {skills.map(s => (
                    <tr key={s.slug} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-mono text-xs text-gray-700">{s.slug}</td>
                      <td className="px-4 py-3 text-gray-500 text-xs truncate max-w-xs">{s.summary || s.name}</td>
                      {isAdmin && (
                        <td className="px-4 py-3 text-right">
                          <button onClick={() => removeSkill(s.slug)} className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
