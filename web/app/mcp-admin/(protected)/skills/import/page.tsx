'use client'

import { useState, useCallback } from 'react'
import Link from 'next/link'
import { ArrowLeft, Upload, FileText, Check, Globe, AlertTriangle } from 'lucide-react'
import { API_BASE } from '@/lib/config'
import type { ParsedSkill } from '@/app/api/skills/import/route'

const FORMAT_LABELS: Record<string, string> = {
  claude: 'Claude',
  copilot: 'Copilot',
  plain: 'Markdown',
}

const FORMAT_COLORS: Record<string, string> = {
  claude: 'bg-orange-50 text-orange-700',
  copilot: 'bg-blue-50 text-blue-700',
  plain: 'bg-gray-100 text-gray-600',
}

export default function SkillImportPage() {
  const [dragging, setDragging] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [importing, setImporting] = useState(false)
  const [skills, setSkills] = useState<ParsedSkill[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [result, setResult] = useState<{ created: number; updated: number; total: number } | null>(null)
  const [error, setError] = useState('')

  const processFiles = useCallback(async (fileList: FileList) => {
    const files = Array.from(fileList).filter(f => f.name.endsWith('.md'))
    if (!files.length) { setError('No .md files found.'); return }

    const contents = await Promise.all(
      files.map(async f => ({ name: f.name, content: await f.text() }))
    )

    setPreviewing(true)
    setError('')
    const res = await fetch(`${API_BASE}/api/skills/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'preview', files: contents }),
    })
    const data = await res.json()
    setPreviewing(false)

    if (!res.ok) { setError(data.error ?? 'Preview failed'); return }
    setSkills(data.skills)
    setSelected(new Set(data.skills.map((s: ParsedSkill) => s.slug)))
  }, [])

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragging(false)
    processFiles(e.dataTransfer.files)
  }

  function onFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files?.length) processFiles(e.target.files)
  }

  function toggleAll() {
    if (selected.size === skills.length) setSelected(new Set())
    else setSelected(new Set(skills.map(s => s.slug)))
  }

  function toggle(slug: string) {
    const next = new Set(selected)
    next.has(slug) ? next.delete(slug) : next.add(slug)
    setSelected(next)
  }

  async function handleImport() {
    setImporting(true)
    const res = await fetch(`${API_BASE}/api/skills/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'confirm', skills, selected: Array.from(selected) }),
    })
    const data = await res.json()
    setImporting(false)
    if (!res.ok) { setError(data.error ?? 'Import failed'); return }
    setResult(data)
  }

  if (result) {
    return (
      <div className="max-w-xl space-y-6">
        <Link href="/panel/mcp-admin/skills" className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900">
          <ArrowLeft className="w-4 h-4" /> Skills
        </Link>
        <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center space-y-4">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-green-500 mb-2">
            <Check className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-xl font-bold text-gray-900">Import complete</h1>
          <div className="flex justify-center gap-6 text-sm">
            <div><span className="text-2xl font-bold text-green-600">{result.created}</span><p className="text-gray-500">Created</p></div>
            <div><span className="text-2xl font-bold text-blue-600">{result.updated}</span><p className="text-gray-500">Updated</p></div>
            <div><span className="text-2xl font-bold text-gray-700">{result.total}</span><p className="text-gray-500">Total</p></div>
          </div>
          <p className="text-sm text-gray-500 flex items-center justify-center gap-1.5">
            <Globe className="w-4 h-4 text-green-600" /> All imported skills are marked as global
          </p>
          <div className="flex gap-3 pt-2">
            <Link href="/panel/mcp-admin/skills"
              className="flex-1 py-2.5 text-sm font-medium text-center bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
              View Skills
            </Link>
            <button onClick={() => { setResult(null); setSkills([]) }}
              className="flex-1 py-2.5 text-sm font-medium border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
              Import More
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/panel/mcp-admin/skills" className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900">
            <ArrowLeft className="w-4 h-4" /> Skills
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">Import Skills</h1>
        </div>
        {skills.length > 0 && (
          <button
            onClick={handleImport}
            disabled={importing || selected.size === 0}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <Globe className="w-4 h-4" />
            {importing ? 'Importing…' : `Import ${selected.size} skill${selected.size !== 1 ? 's' : ''}`}
          </button>
        )}
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 text-sm text-blue-800">
        Supports <strong>Claude skills</strong> (frontmatter: <code>name</code> + <code>description</code>),
        <strong> Copilot instructions</strong> (<code>applyTo</code>), and plain Markdown.
        All imported skills are set as <strong>global</strong> — visible to all users in the portal.
      </div>

      {error && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" /> {error}
        </div>
      )}

      {skills.length === 0 ? (
        <label
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`flex flex-col items-center justify-center gap-4 p-12 rounded-2xl border-2 border-dashed cursor-pointer transition-colors ${
            dragging ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-gray-400 bg-white'
          }`}
        >
          <Upload className={`w-10 h-10 ${dragging ? 'text-blue-500' : 'text-gray-400'}`} />
          <div className="text-center">
            <p className="text-sm font-medium text-gray-700">
              {previewing ? 'Parsing files…' : 'Drop .md files here or click to browse'}
            </p>
            <p className="text-xs text-gray-400 mt-1">Supports multiple files — Claude, Copilot, plain Markdown</p>
          </div>
          <input type="file" accept=".md" multiple onChange={onFileInput} className="hidden" />
        </label>
      ) : (
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
            <p className="text-sm font-semibold text-gray-900">{skills.length} files parsed</p>
            <button onClick={toggleAll} className="text-xs text-blue-600 hover:underline">
              {selected.size === skills.length ? 'Deselect all' : 'Select all'}
            </button>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="w-10 px-4 py-2"></th>
                <th className="text-left px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">Slug / Name</th>
                <th className="text-left px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">Summary</th>
                <th className="text-left px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">Format</th>
                <th className="text-left px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {skills.map(s => (
                <tr key={s.slug} className={`hover:bg-gray-50 transition-colors ${!selected.has(s.slug) ? 'opacity-40' : ''}`}>
                  <td className="px-4 py-3">
                    <input type="checkbox" checked={selected.has(s.slug)} onChange={() => toggle(s.slug)}
                      className="rounded border-gray-300" />
                  </td>
                  <td className="px-4 py-3">
                    <p className="font-mono text-xs text-gray-500">{s.slug}</p>
                    <p className="text-sm font-medium text-gray-900">{s.name}</p>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 max-w-xs truncate">{s.summary || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${FORMAT_COLORS[s.format]}`}>
                      {FORMAT_LABELS[s.format]}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {s.conflict ? (
                      <span className="flex items-center gap-1 text-xs text-amber-600">
                        <AlertTriangle className="w-3.5 h-3.5" /> Will overwrite
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-xs text-green-600">
                        <FileText className="w-3.5 h-3.5" /> New
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
