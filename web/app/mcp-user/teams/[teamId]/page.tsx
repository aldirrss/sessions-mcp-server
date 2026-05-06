'use client'

import { useState, useEffect, useCallback, use } from 'react'
import { Users, Key, BookOpen, MessageSquare, Trash2, Plus, Copy, Check, Link2, Clock } from 'lucide-react'
import UserPortalHeader from '@/components/user-portal-header'

type Tab = 'sessions' | 'members' | 'tokens' | 'skills'
type Member = { id: string; username: string; email: string; role: string; joined_at: string }
type Token  = { id: string; name: string; revoked: boolean; created_at: string }
type Session = { session_id: string; title: string; notes_count: number; updated_at: string }
type Skill   = { slug: string; name: string; summary: string }
type Invite  = { token: string; expires_at: string; created_at: string; used_at: string | null; used_by_username: string | null }

export default function TeamAdminPage({ params }: { params: Promise<{ teamId: string }> }) {
  const { teamId } = use(params)
  const [tab, setTab] = useState<Tab>('sessions')
  const [teamName, setTeamName] = useState('')
  const [role, setRole] = useState('')
  const [members, setMembers] = useState<Member[]>([])
  const [tokens, setTokens] = useState<Token[]>([])
  const [sessions, setSessions] = useState<Session[]>([])
  const [skills, setSkills] = useState<Skill[]>([])
  const [invites, setInvites] = useState<Invite[]>([])
  const [newToken, setNewToken] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [copiedInvite, setCopiedInvite] = useState<string | null>(null)
  const [addUsername, setAddUsername] = useState('')
  const [addSkugSlug, setAddSkillSlug] = useState('')
  const [error, setError] = useState('')

  const API = `/panel/api/teams/${teamId}`

  const fetchTeam = useCallback(async () => {
    const res = await fetch(API)
    if (res.status === 401) { window.location.href = '/panel/mcp-user/login'; return }
    if (res.ok) { const d = await res.json(); setTeamName(d.name); setRole(d.role) }
  }, [API])

  const fetchMembers  = useCallback(async () => { const r = await fetch(`${API}/members`);  if (r.ok) setMembers(await r.json()) }, [API])
  const fetchTokens   = useCallback(async () => { const r = await fetch(`${API}/tokens`);   if (r.ok) setTokens(await r.json()) }, [API])
  const fetchSessions = useCallback(async () => { const r = await fetch(`${API}/sessions`); if (r.ok) setSessions(await r.json()) }, [API])
  const fetchSkills   = useCallback(async () => { const r = await fetch(`${API}/skills`);   if (r.ok) setSkills(await r.json()) }, [API])
  const fetchInvites  = useCallback(async () => { const r = await fetch(`${API}/invites`);  if (r.ok) setInvites(await r.json()) }, [API])

  useEffect(() => {
    fetchTeam(); fetchSessions(); fetchMembers(); fetchTokens(); fetchSkills(); fetchInvites()
  }, [fetchTeam, fetchSessions, fetchMembers, fetchTokens, fetchSkills, fetchInvites])

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

  async function createInvite() {
    const res = await fetch(`${API}/invites`, { method: 'POST' })
    const data = await res.json()
    if (res.ok) {
      const link = `${window.location.origin}/panel/mcp-user/invite/${data.token}`
      await navigator.clipboard.writeText(link)
      setCopiedInvite(data.token)
      setTimeout(() => setCopiedInvite(null), 3000)
      fetchInvites()
    }
  }

  async function revokeInvite(token: string) {
    if (!confirm('Revoke this invite link?')) return
    await fetch(`${API}/invites/${token}`, { method: 'DELETE' })
    fetchInvites()
  }

  async function copyInviteLink(token: string) {
    const link = `${window.location.origin}/panel/mcp-user/invite/${token}`
    await navigator.clipboard.writeText(link)
    setCopiedInvite(token)
    setTimeout(() => setCopiedInvite(null), 2000)
  }

  const isAdmin = role === 'admin'
  const TABS: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: 'sessions', label: 'Sessions', icon: <MessageSquare className="w-3.5 h-3.5" /> },
    { key: 'members',  label: 'Members',  icon: <Users className="w-3.5 h-3.5" /> },
    { key: 'tokens',   label: 'Tokens',   icon: <Key className="w-3.5 h-3.5" /> },
    { key: 'skills',   label: 'Skills',   icon: <BookOpen className="w-3.5 h-3.5" /> },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      <UserPortalHeader
        title={teamName || 'Team'}
        subtitle={role ? `Your role: ${role}` : 'Loading…'}
        accentColor="bg-blue-600"
      />

      <main className="max-w-3xl mx-auto px-4 py-5 md:px-6 md:py-6 space-y-4">
        {newToken && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-2">
            <p className="text-sm font-semibold text-amber-800">⚠️ Copy this token now — it will not be shown again</p>
            <div className="flex gap-2">
              <code className="flex-1 bg-gray-900 text-green-400 px-3 py-2 rounded-lg text-xs font-mono break-all">{newToken}</code>
              <button onClick={() => copyToken(newToken)} className="flex-shrink-0 p-2 rounded-lg border border-amber-200 bg-white hover:bg-amber-50">
                {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4 text-gray-500" />}
              </button>
            </div>
            <button onClick={() => setNewToken(null)} className="text-xs text-amber-700 hover:underline">Dismiss</button>
          </div>
        )}

        {error && <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>}

        {/* Team tab card */}
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
          <div className="flex overflow-x-auto scrollbar-none border-b border-gray-100">
            {TABS.map(t => (
              <button key={t.key} onClick={() => setTab(t.key)}
                className={`flex items-center gap-1.5 px-4 py-3 text-sm font-medium border-b-2 whitespace-nowrap transition-colors flex-shrink-0 -mb-px ${
                  tab === t.key ? 'border-blue-600 text-blue-700' : 'border-transparent text-gray-500 hover:text-gray-900'
                }`}>
                {t.icon}{t.label}
              </button>
            ))}
          </div>

          {/* Sessions */}
          {tab === 'sessions' && (
            sessions.length === 0 ? (
              <div className="p-8 text-center text-sm text-gray-400">No team sessions yet.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm min-w-[480px]">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Session ID</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Title</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Notes</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase hidden sm:table-cell">Updated</th>
                      {isAdmin && <th className="px-4 py-3" />}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {sessions.map(s => (
                      <tr key={s.session_id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 font-mono text-xs text-gray-500">{s.session_id}</td>
                        <td className="px-4 py-3 text-gray-900 font-medium">{s.title}</td>
                        <td className="px-4 py-3 text-gray-500">{s.notes_count}</td>
                        <td className="px-4 py-3 text-gray-400 text-xs hidden sm:table-cell">{new Date(s.updated_at).toLocaleDateString()}</td>
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
              </div>
            )
          )}

          {/* Members */}
          {tab === 'members' && (
            <div>
              {isAdmin && (
                <div className="p-4 border-b border-gray-100 space-y-3">
                  {/* Add by username */}
                  <form onSubmit={addMember} className="flex gap-2">
                    <input type="text" value={addUsername} onChange={e => setAddUsername(e.target.value)} required
                      placeholder="Add member by username"
                      className="flex-1 px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    <button type="submit" className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors flex-shrink-0">
                      <Plus className="w-4 h-4" /> <span className="hidden sm:inline">Add</span>
                    </button>
                  </form>
                  {/* Invite via link */}
                  <button onClick={createInvite}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50 transition-colors w-full sm:w-auto">
                    <Link2 className="w-4 h-4" />
                    {copiedInvite ? 'Link copied!' : 'Create invite link'}
                  </button>
                </div>
              )}

              {/* Active invite links (admin only) */}
              {isAdmin && invites.filter(i => !i.used_at && new Date(i.expires_at) > new Date()).length > 0 && (
                <div className="px-4 py-3 bg-blue-50 border-b border-gray-100">
                  <p className="text-xs font-semibold text-blue-700 mb-2">Active invite links</p>
                  <div className="space-y-2">
                    {invites.filter(i => !i.used_at && new Date(i.expires_at) > new Date()).map(inv => (
                      <div key={inv.token} className="flex items-center gap-2">
                        <code className="flex-1 text-xs font-mono text-gray-600 bg-white border border-gray-200 px-2 py-1.5 rounded-lg truncate">
                          {window.location.origin}/panel/mcp-user/invite/{inv.token}
                        </code>
                        <button onClick={() => copyInviteLink(inv.token)}
                          className="flex-shrink-0 p-1.5 rounded-md border border-gray-200 bg-white hover:bg-gray-50 transition-colors"
                          title="Copy link">
                          {copiedInvite === inv.token ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5 text-gray-500" />}
                        </button>
                        <button onClick={() => revokeInvite(inv.token)}
                          className="flex-shrink-0 p-1.5 rounded-md border border-gray-200 bg-white hover:bg-red-50 hover:text-red-600 transition-colors"
                          title="Revoke">
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                        <span className="flex-shrink-0 flex items-center gap-1 text-xs text-gray-400">
                          <Clock className="w-3 h-3" />
                          {new Date(inv.expires_at).toLocaleDateString()}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {members.length === 0 ? (
                <div className="p-8 text-center text-sm text-gray-400">No members yet.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm min-w-[360px]">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Username</th>
                        <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase hidden sm:table-cell">Email</th>
                        <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Role</th>
                        {isAdmin && <th className="px-4 py-3" />}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {members.map(m => (
                        <tr key={m.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-medium text-gray-900">{m.username}</td>
                          <td className="px-4 py-3 text-gray-500 hidden sm:table-cell">{m.email}</td>
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
              )}
            </div>
          )}

          {/* Tokens */}
          {tab === 'tokens' && (
            <div>
              {isAdmin && (
                <div className="p-4 border-b border-gray-100">
                  <button onClick={createToken} className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors">
                    <Plus className="w-4 h-4" /> New Token
                  </button>
                </div>
              )}
              {tokens.length === 0 ? (
                <div className="p-8 text-center text-sm text-gray-400">No tokens yet.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm min-w-[320px]">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Name</th>
                        <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Status</th>
                        <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase hidden sm:table-cell">Created</th>
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
                          <td className="px-4 py-3 text-gray-400 text-xs hidden sm:table-cell">{new Date(t.created_at).toLocaleDateString()}</td>
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
                </div>
              )}
            </div>
          )}

          {/* Skills */}
          {tab === 'skills' && (
            <div>
              {isAdmin && (
                <form onSubmit={addSkill} className="flex gap-2 p-4 border-b border-gray-100">
                  <input type="text" value={addSkugSlug} onChange={e => setAddSkillSlug(e.target.value)} required
                    placeholder="Skill slug (e.g. python)"
                    className="flex-1 px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                  <button type="submit" className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors flex-shrink-0">
                    <Plus className="w-4 h-4" /> <span className="hidden sm:inline">Add</span>
                  </button>
                </form>
              )}
              {skills.length === 0 ? (
                <div className="p-8 text-center text-sm text-gray-400">No skills added to this team yet.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm min-w-[320px]">
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
                          <td className="px-4 py-3 font-mono text-xs text-gray-700 whitespace-nowrap">{s.slug}</td>
                          <td className="px-4 py-3 text-gray-500 text-xs">{s.summary || s.name}</td>
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
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
