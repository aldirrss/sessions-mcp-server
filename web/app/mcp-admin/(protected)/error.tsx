'use client'

import { useEffect } from 'react'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error(error)
  }, [error])

  return (
    <div className="flex flex-col items-center justify-center min-h-[200px] gap-4">
      <p className="text-sm text-red-600 font-medium">Something went wrong.</p>
      <button
        onClick={reset}
        className="px-4 py-2 text-sm bg-gray-900 text-white rounded-lg hover:bg-gray-700 transition-colors"
      >
        Try again
      </button>
    </div>
  )
}
