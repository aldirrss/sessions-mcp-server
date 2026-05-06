'use client'

import { useState } from 'react'
import { X } from 'lucide-react'

type NoteCardProps = {
  id: number
  content: string
  source: string
  created_at: string
  pinned?: boolean
}

const EXPANDABLE_THRESHOLD = 120

function isExpandable(content: string) {
  return content.length > EXPANDABLE_THRESHOLD || content.split('\n').length > 2
}

export default function NoteCard({ content, source, created_at, pinned = false }: NoteCardProps) {
  const [open, setOpen] = useState(false)
  const expandable = isExpandable(content)

  const bg = pinned ? 'bg-blue-50 border-blue-100' : 'bg-gray-50 border-gray-100'

  return (
    <>
      <div className={`group border rounded-xl p-3 ${bg}`}>
        <p className="text-sm text-gray-900 whitespace-pre-wrap line-clamp-2">{content}</p>
        <div className="flex items-center justify-between mt-1.5">
          <p className="text-xs text-gray-400">{source} · {new Date(created_at).toLocaleString()}</p>
          {expandable && (
            <button
              onClick={() => setOpen(true)}
              className="text-xs text-blue-600 hover:text-blue-800 opacity-0 group-hover:opacity-100 transition-opacity ml-2 flex-shrink-0"
            >
              Read more
            </button>
          )}
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
