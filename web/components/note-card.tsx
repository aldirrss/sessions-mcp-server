'use client'

import { useState } from 'react'
import { X } from 'lucide-react'

type NoteCardProps = {
  id: number
  content: string
  source: string
  created_at: string
  pinned?: boolean
  onTogglePin?: (id: number, pinned: boolean) => void
  togglingPin?: boolean
}

const EXPANDABLE_THRESHOLD = 120

function isExpandable(content: string) {
  return content.length > EXPANDABLE_THRESHOLD || content.split('\n').length > 2
}

export default function NoteCard({ content, source, created_at, pinned = false, onTogglePin, togglingPin }: NoteCardProps) {
  const [open, setOpen] = useState(false)
  const expandable = isExpandable(content)

  const bg = pinned ? 'bg-amber-50 border-amber-200' : 'bg-gray-50 border-gray-100'

  return (
    <>
      <div className={`group border rounded-xl p-3 ${bg}`}>
        <p className="text-sm text-gray-900 whitespace-pre-wrap line-clamp-2">{content}</p>
        <div className="flex items-center justify-between mt-1.5 gap-2">
          <p className="text-xs text-gray-400 min-w-0 truncate">
            {pinned && <span className="text-amber-600 font-medium mr-1">📌</span>}
            {source} · {new Date(created_at).toLocaleString()}
          </p>
          <div className="flex items-center gap-2 flex-shrink-0">
            {onTogglePin && (
              <button
                onClick={() => onTogglePin(id, pinned)}
                disabled={togglingPin}
                className={`text-xs px-2 py-0.5 rounded transition-colors disabled:opacity-40 ${
                  pinned ? 'text-amber-600 hover:bg-amber-100' : 'text-gray-400 hover:text-amber-600 hover:bg-amber-50'
                }`}
              >
                {pinned ? 'Unpin' : 'Pin'}
              </button>
            )}
            {expandable && (
              <button
                onClick={() => setOpen(true)}
                className="text-xs text-blue-600 hover:text-blue-800 opacity-0 group-hover:opacity-100 transition-opacity"
              >
                Read more
              </button>
            )}
          </div>
        </div>
      </div>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setOpen(false)}
        >
          <div
            className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[80vh] flex flex-col"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <p className="text-xs text-gray-400">{source} · {new Date(created_at).toLocaleString()}</p>
              <button onClick={() => setOpen(false)}
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="overflow-y-auto px-5 py-4">
              <p className="text-sm text-gray-900 whitespace-pre-wrap">{content}</p>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
