'use client'

import { useState, useEffect, useCallback } from 'react'
import { Plus, Trash2, Edit2, Check, X, Settings2 } from 'lucide-react'

import { API_BASE } from '@/lib/config'

type ConfigEntry = {
  key: string
  value: string
  description: string
  updated_at: string
}

export default function ConfigPage() {
  const [rows, setRows] = useState<ConfigEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ key: '', value: '', description: '' })
  const [creating, setCreating] = useState(false)
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [editForm, setEditForm] = useState({ value: '', description: '' })
  const [saving, setSaving] = useState(false)

  const fetchConfig = useCallback(async () => {
    setLoading(true)
    const res = await fetch(`${API_BASE}/api/config`)
    const data = await res.json()
    setRows(data.rows)
    setLoading(false)
  }, [])

  useEffect(() => { fetchConfig() }, [fetchConfig])

  function startEdit(entry: ConfigEntry) {
    setEditingKey(entry.key)
    setEditForm({ value: entry.value, description: entry.description })
  }

  async function handleSave(key: string) {
    setSaving(true)
    await fetch(`${API_BASE}/api/config/${encodeURIComponent(key)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editForm),
    })
    setSaving(false)
    setEditingKey(null)
    fetchConfig()
  }

  async function handleDelete(key: string) {
    if (!confirm(`Delete config key "${key}"?`)) return
    await fetch(`${API_BASE}/api/config/${encodeURIComponent(key)}`, { method: 'DELETE' })
    fetchConfig()
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setCreating(true)
    await fetch(`${API_BASE}/api/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    setShowCreate(false)
    setForm({ key: '', value: '', description: '' })
    setCreating(false)
    fetchConfig()
  }

  return (
    <div className="max-w-4xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Settings2 className="w-6 h-6 text-gray-500" /> Config
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Global key-value settings — loaded by Claude at conversation start via <code className="text-xs bg-gray-100 px-1 rounded">config_list</code>
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" /> New Entry
        </button>
      </div>

      <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-sm text-gray-400">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-400">
            No config entries yet. Create one to store Claude instructions or settings.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-52">Key</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Value</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-48">Description</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-24">Updated</th>
                <th className="px-4 py-3 w-20"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((entry) => (
                <tr key={entry.key} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-mono text-xs text-gray-600 align-top">{entry.key}</td>
                  <td className="px-4 py-3 align-top">
                    {editingKey === entry.key ? (
                      <textarea
                        value={editForm.value}
                        onChange={e => setEditForm(f => ({ ...f, value: e.target.value }))}
                        rows={3}
                        className="w-full px-2 py-1 text-sm rounded border border-gray-300 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    ) : (
                      <p className="text-sm text-gray-900 whitespace-pre-wrap break-words">{entry.value}</p>
                    )}
                  </td>
                  <td className="px-4 py-3 align-top">
                    {editingKey === entry.key ? (
                      <input
                        value={editForm.description}
                        onChange={e => setEditForm(f => ({ ...f, description: e.target.value }))}
                        placeholder="What this controls"
                        className="w-full px-2 py-1 text-sm rounded border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    ) : (
                      <p className="text-xs text-gray-500">{entry.description || '—'}</p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400 align-top whitespace-nowrap">
                    {new Date(entry.updated_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 align-top">
                    {editingKey === entry.key ? (
                      <div className="flex items-center gap-1">
                        <button onClick={() => handleSave(entry.key)} disabled={saving}
                          className="p-1.5 rounded-md bg-blue-50 hover:bg-blue-100 text-blue-600 disabled:opacity-60">
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => setEditingKey(null)}
                          className="p-1.5 rounded-md hover:bg-gray-100 text-gray-500">
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1">
                        <button onClick={() => startEdit(entry)}
                          className="p-1.5 rounded-md hover:bg-gray-100 text-gray-500 hover:text-gray-900">
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => handleDelete(entry.key)}
                          className="p-1.5 rounded-md hover:bg-red-50 text-gray-500 hover:text-red-600">
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showCreate && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <form onSubmit={handleCreate} className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-lg space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">New Config Entry</h2>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Key</label>
              <input
                required
                value={form.key}
                onChange={e => setForm(f => ({ ...f, key: e.target.value }))}
                placeholder="claude_project_instructions"
                className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Value</label>
              <textarea
                required
                value={form.value}
                onChange={e => setForm(f => ({ ...f, value: e.target.value }))}
                rows={4}
                placeholder="Value to store…"
                className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description <span className="text-gray-400 font-normal">(optional)</span></label>
              <input
                value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                placeholder="What this config controls"
                className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setShowCreate(false)}
                className="px-4 py-2 text-sm rounded-lg border border-gray-300 hover:bg-gray-50">Cancel</button>
              <button type="submit" disabled={creating}
                className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-60">
                {creating ? 'Creating…' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
