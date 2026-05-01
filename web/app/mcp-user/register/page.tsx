'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { UserPlus, Copy, Check, Terminal, Code2 } from 'lucide-react'

type TokenResult = { token: string; username: string }

export default function RegisterPage() {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<TokenResult | null>(null)
  const [copied, setCopied] = useState(false)
  const [mcpUrl, setMcpUrl] = useState('')

  useEffect(() => { setMcpUrl(`${window.location.origin}/mcp`) }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (password !== confirm) { setError('Passwords do not match.'); return }
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return }
    setLoading(true)
    const res = await fetch('/panel/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password }),
    })
    const data = await res.json()
    setLoading(false)
    if (!res.ok) { setError(data.error ?? 'Registration failed.'); return }
    setResult({ token: data.token, username: data.username })
  }

  async function copyToken() {
    if (!result) return
    await navigator.clipboard.writeText(result.token)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (result) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
        <div className="w-full max-w-lg">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 space-y-6">
            <div className="text-center">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-green-500 mb-4">
                <Check className="w-6 h-6 text-white" />
              </div>
              <h1 className="text-2xl font-bold text-gray-900">Account Created!</h1>
              <p className="text-sm text-gray-500 mt-1">Welcome, <strong>{result.username}</strong></p>
            </div>

            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <p className="text-sm font-semibold text-amber-800 mb-1">⚠️ Save your token now</p>
              <p className="text-xs text-amber-700">This token will NOT be shown again. Copy it and store it safely.</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Your Access Token</label>
              <div className="flex items-center gap-2">
                <code className="flex-1 bg-gray-900 text-green-400 px-3 py-2.5 rounded-lg text-xs font-mono break-all select-all">
                  {result.token}
                </code>
                <button onClick={copyToken}
                  className="flex-shrink-0 p-2.5 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors">
                  {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4 text-gray-500" />}
                </button>
              </div>
            </div>

            <div className="space-y-3">
              <p className="text-sm font-medium text-gray-700">Connect via:</p>
              <div className="space-y-2">
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1.5">
                    <Terminal className="w-3.5 h-3.5 text-gray-500" />
                    <span className="text-xs font-semibold text-gray-600">Claude Code CLI</span>
                  </div>
                  <code className="text-xs text-gray-700 font-mono break-all">
                    claude mcp add lm-mcp-ai --transport http --url {mcpUrl} --header &quot;Authorization: Bearer {result.token}&quot;
                  </code>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1.5">
                    <Code2 className="w-3.5 h-3.5 text-gray-500" />
                    <span className="text-xs font-semibold text-gray-600">VSCode / .claude/mcp.json</span>
                  </div>
                  <code className="text-xs text-gray-700 font-mono whitespace-pre">
{`{
  "mcpServers": {
    "lm-mcp-ai": {
      "type": "http",
      "url": "${mcpUrl}",
      "headers": { "Authorization": "Bearer ${result.token}" }
    }
  }
}`}
                  </code>
                </div>
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <Link href="/mcp-user/login"
                className="flex-1 text-center py-2.5 text-sm font-medium text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50 transition-colors">
                Go to Portal
              </Link>
              <Link href="/mcp-admin/login"
                className="flex-1 text-center py-2.5 text-sm font-medium text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
                Admin Panel
              </Link>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-blue-600 mb-4">
            <UserPlus className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Create Account</h1>
          <p className="text-sm text-gray-500 mt-1">Get access to lm-mcp-ai</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 space-y-4">
          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Username</label>
            <input type="text" value={username} onChange={e => setUsername(e.target.value)} required autoFocus
              className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="yourname" />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} required
              className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="you@example.com" />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Password</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} required
              className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Min. 8 characters" />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Confirm Password</label>
            <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} required
              className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>

          <button type="submit" disabled={loading}
            className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white text-sm font-medium rounded-lg transition-colors">
            {loading ? 'Creating account…' : 'Create account'}
          </button>

          <p className="text-center text-xs text-gray-500">
            Already have an account?{' '}
            <Link href="/mcp-user/login" className="text-blue-600 hover:underline">Sign in</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
