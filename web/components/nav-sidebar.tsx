'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { LayoutDashboard, MessageSquare, BookOpen, LogOut } from 'lucide-react'
import { cn } from '@/lib/cn'

const API_BASE = '/panel/mcp-admin'

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { href: '/sessions', label: 'Sessions', icon: MessageSquare },
  { href: '/skills', label: 'Skills', icon: BookOpen },
]

export default function NavSidebar() {
  const pathname = usePathname()

  async function handleLogout() {
    await fetch(`${API_BASE}/api/auth/logout`, { method: 'POST' })
    window.location.href = `${API_BASE}/login`
  }

  return (
    <aside className="fixed inset-y-0 left-0 w-60 bg-white border-r border-gray-200 flex flex-col z-10">
      <div className="px-5 py-5 border-b border-gray-100">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">MCP Admin</p>
        <p className="text-sm font-semibold text-gray-900 mt-0.5">lm-mcp-ai</p>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {navItems.map(({ href, label, icon: Icon, exact }) => {
          const active = exact ? pathname === href : pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                active
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {label}
            </Link>
          )
        })}
      </nav>

      <div className="px-3 py-4 border-t border-gray-100">
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-100 hover:text-gray-900 transition-colors w-full"
        >
          <LogOut className="w-4 h-4 flex-shrink-0" />
          Sign out
        </button>
      </div>
    </aside>
  )
}
