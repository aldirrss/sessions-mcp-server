'use client'

import { useState, useEffect, useCallback } from 'react'
import { Plus, Trash2, Copy, Check, Key, Terminal, Code2, Github } from 'lucide-react'

import { API_BASE } from '@/lib/config'
import UserPortalHeader from '@/components/user-portal-header'

type Token = {
  id: string; name: string; token_prefix: string | null; last_used_at: string | null
  expires_at: string | null; revoked: boolean; created_at: string
}

export default function PortalPage() {
  const [tokens, setTokens] = useState<Token[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newExpires, setNewExpires] = useState('')
  const [creating, setCreating] = useState(false)
  const [newToken, setNewToken] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [revoking, setRevoking] = useState<string | null>(null)
  const [githubHasToken, setGithubHasToken] = useState(false)
  const [githubInput, setGithubInput] = useState('')
  const [githubEditing, setGithubEditing] = useState(false)
  const [githubSaving, setGithubSaving] = useState(false)

  const fetchTokens = useCallback(async () => {
    const res = await fetch(`${API_BASE}/portal/tokens`)
    if (res.status === 401) { window.location.href = '/panel/mcp-user/login'; return }
    const data = await res.json()
    setTokens(data.tokens ?? [])
    setLoading(false)
  }, [])

  const fetchGithubStatus = useCallback(async () => {
    const res = await fetch(`${API_BASE}/portal/github-token`)
    if (res.ok) { const d = await res.json(); setGithubHasToken(d.has_token) }
  }, [])

  useEffect(() => { fetchTokens(); fetchGithubStatus() }, [fetchTokens, fetchGithubStatus])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setCreating(true)
    const res = await fetch(`${API_BASE}/portal/tokens`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newName, expires_days: newExpires ? Number(newExpires) : null }),
    })
    const data = await res.json()
    setCreating(false); setShowCreate(false)
    setNewName(''); setNewExpires('')
    setNewToken(data.token)
    fetchTokens()
  }

  async function handleRevoke(id: string) {
    if (!confirm('Revoke this token? It will stop working immediately.')) return
    setRevoking(id)
    await fetch(`${API_BASE}/portal/tokens/${id}`, { method: 'DELETE' })
    setRevoking(null)
    fetchTokens()
  }

  async function copyToken(token: string) {
    await navigator.clipboard.writeText(token)
    setCopied(true); setTimeout(() => setCopied(false), 2000)
  }

  async function handleSaveGithubToken() {
    if (!githubInput.trim()) return
    setGithubSaving(true)
    await fetch(`${API_BASE}/portal/github-token`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: githubInput.trim() }),
    })
    setGithubSaving(false); setGithubEditing(false); setGithubInput('')
    fetchGithubStatus()
  }

  async function handleRemoveGithubToken() {
    if (!confirm('Remove your GitHub token?')) return
    await fetch(`${API_BASE}/portal/github-token`, { method: 'DELETE' })
    setGithubHasToken(false)
  }

  const activeTokens = tokens.filter(t => !t.revoked)
  const revokedTokens = tokens.filter(t => t.revoked)

  return (
    <div className="min-h-screen bg-gray-50">
      <UserPortalHeader title="MCP Portal" subtitle="Manage your access tokens" accentColor="bg-blue-600" />

      <main className="max-w-3xl mx-auto px-4 py-5 md:px-6 md:py-6 space-y-5">

        {/* New token alert */}
        {newToken && (
          <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 md:p-5 space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-amber-800">⚠️ Save this token — won&apos;t be shown again</p>
              <button onClick={() => setNewToken(null)} className="text-amber-500 hover:text-amber-700 text-lg leading-none">✕</button>
            </div>
            <div className="flex items-center gap-2">
              <code className="flex-1 bg-gray-900 text-green-400 px-3 py-2 rounded-lg text-xs font-mono break-all">{newToken}</code>
              <button onClick={() => copyToken(newToken)}
                className="flex-shrink-0 p-2 rounded-lg border border-amber-200 bg-white hover:bg-amber-50">
                {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4 text-amber-600" />}
              </button>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              <div className="bg-white rounded-xl border border-gray-200 p-3">
                <div className="flex items-center gap-1.5 mb-1.5">
                  <Terminal className="w-3.5 h-3.5 text-gray-400" />
                  <span className="text-xs font-semibold text-gray-500">Claude Code CLI</span>
                </div>
                <code className="text-[10px] text-gray-600 font-mono break-all leading-relaxed">
                  --header &quot;Authorization: Bearer {newToken.slice(0, 20)}…&quot;
                </code>
              </div>
              <div className="bg-white rounded-xl border border-gray-200 p-3">
                <div className="flex items-center gap-1.5 mb-1.5">
                  <Code2 className="w-3.5 h-3.5 text-gray-400" />
                  <span className="text-xs font-semibold text-gray-500">VSCode mcp.json</span>
                </div>
                <code className="text-[10px] text-gray-600 font-mono break-all leading-relaxed">
                  &quot;Authorization&quot;: &quot;Bearer {newToken.slice(0, 20)}…&quot;
                </code>
              </div>
            </div>
          </div>
        )}

        {/* Active tokens */}
        <div className="bg-white rounded-2xl border border-gray-200">
          <div className="p-4 md:p-5 flex items-center justify-between border-b border-gray-100">
            <div>
              <h2 className="text-sm font-semibold text-gray-900">Active Tokens ({activeTokens.length})</h2>
              <p className="text-xs text-gray-400 mt-0.5">Sessions created with this token are private — only you can access them.</p>
            </div>
            <button onClick={() => setShowCreate(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
              <Plus className="w-4 h-4" />
              <span className="hidden sm:inline">New token</span>
            </button>
          </div>
          {loading ? (
            <p className="text-sm text-gray-400 p-5">Loading…</p>
          ) : activeTokens.length === 0 ? (
            <p className="text-sm text-gray-400 p-5">No active tokens.</p>
          ) : (
            <div className="divide-y divide-gray-100">
              {activeTokens.map(t => (
                <div key={t.id} className="flex items-center justify-between px-4 md:px-5 py-3.5 gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{t.name}</p>
                    <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                      <code className="text-xs font-mono text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">
                        {t.token_prefix ? `${t.token_prefix}••••••••` : '••••••••'}
                      </code>
                      <span className="text-xs text-gray-400">
                        Created {new Date(t.created_at).toLocaleDateString()}
                        {t.last_used_at && ` · Used ${new Date(t.last_used_at).toLocaleDateString()}`}
                        {t.expires_at && ` · Expires ${new Date(t.expires_at).toLocaleDateString()}`}
                        {!t.expires_at && ' · No expiry'}
                      </span>
                    </div>
                  </div>
                  <button onClick={() => handleRevoke(t.id)} disabled={revoking === t.id}
                    className="flex-shrink-0 p-1.5 rounded-md hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors disabled:opacity-40">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Revoked tokens */}
        {revokedTokens.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-200 opacity-60">
            <div className="p-4 md:p-5 border-b border-gray-100">
              <h2 className="text-sm font-semibold text-gray-500">Revoked ({revokedTokens.length})</h2>
            </div>
            <div className="divide-y divide-gray-100">
              {revokedTokens.map(t => (
                <div key={t.id} className="flex items-center px-4 md:px-5 py-3 gap-3">
                  <p className="text-sm line-through text-gray-400 flex-1 truncate">{t.name}</p>
                  <span className="text-xs text-red-400 flex-shrink-0">Revoked</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* GitHub PAT */}
        <div className="bg-white rounded-2xl border border-gray-200">
          <div className="p-4 md:p-5 border-b border-gray-100 flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
              <Github className="w-4 h-4 text-gray-500" /> GitHub Token
            </h2>
            {githubHasToken && !githubEditing && (
              <div className="flex items-center gap-2 flex-shrink-0">
                <button onClick={() => setGithubEditing(true)} className="text-xs text-blue-600 hover:underline">Replace</button>
                <button onClick={handleRemoveGithubToken} className="text-xs text-red-500 hover:underline">Remove</button>
              </div>
            )}
          </div>
          <div className="p-4 md:p-5">
            {githubEditing ? (
              <div className="space-y-3">
                <p className="text-xs text-gray-500">
                  Generate at <a href="https://github.com/settings/tokens" target="_blank" rel="noopener noreferrer"
                    className="text-blue-600 hover:underline">github.com/settings/tokens</a>.
                  Scope: <code className="bg-gray-100 px-1 rounded">repo</code> (read-only).
                </p>
                <div className="flex flex-col sm:flex-row gap-2">
                  <input type="password" value={githubInput} onChange={e => setGithubInput(e.target.value)}
                    placeholder="ghp_xxxxxxxxxxxxxxxxxxxx" autoFocus
                    className="flex-1 px-3 py-2 rounded-lg border border-gray-300 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" />
                  <div className="flex gap-2">
                    <button onClick={handleSaveGithubToken} disabled={githubSaving || !githubInput.trim()}
                      className="flex-1 sm:flex-none px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-60">
                      {githubSaving ? 'Saving…' : 'Save'}
                    </button>
                    <button onClick={() => { setGithubEditing(false); setGithubInput('') }}
                      className="flex-1 sm:flex-none px-3 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50">Cancel</button>
                  </div>
                </div>
              </div>
            ) : githubHasToken ? (
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-green-500 flex-shrink-0" />
                <p className="text-sm text-gray-700">Token saved — GitHub tools use your personal token.</p>
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-sm text-gray-400">No token set. GitHub tools use the server default.</p>
                <button onClick={() => setGithubEditing(true)} className="text-sm text-blue-600 hover:underline">Add your GitHub token</button>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Create token modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/40 flex items-end sm:items-center justify-center z-50 p-4">
          <form onSubmit={handleCreate} className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-md space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">New Token</h2>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Token name</label>
              <input required value={newName} onChange={e => setNewName(e.target.value)}
                placeholder="e.g. VSCode laptop, CLI server" autoFocus
                className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Expires in (days) — optional</label>
              <input type="number" min="1" max="3650" value={newExpires} onChange={e => setNewExpires(e.target.value)}
                placeholder="Leave blank for no expiry"
                className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div className="flex gap-2 pt-1">
              <button type="button" onClick={() => setShowCreate(false)}
                className="flex-1 px-4 py-2 text-sm rounded-lg border border-gray-300 hover:bg-gray-50">Cancel</button>
              <button type="submit" disabled={creating}
                className="flex-1 px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-60">
                {creating ? 'Creating…' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
