'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Key, BookOpen, Users, LogOut } from 'lucide-react'
import { cn } from '@/lib/cn'
import { API_BASE } from '@/lib/config'

const NAV_ITEMS = [
  { href: '/mcp-user/portal', label: 'Tokens', icon: Key },
  { href: '/mcp-user/skills', label: 'Skills', icon: BookOpen },
  { href: '/mcp-user/portal/teams', label: 'Teams', icon: Users },
]

interface UserPortalHeaderProps {
  title: string
  subtitle: string
  accentColor?: string
}

export default function UserPortalHeader({ title, subtitle, accentColor = 'bg-blue-600' }: UserPortalHeaderProps) {
  const pathname = usePathname()

  async function handleLogout() {
    await fetch(`${API_BASE}/auth/user-logout`, { method: 'POST' })
    window.location.href = '/panel/mcp-user/login'
  }

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
      {/* Top row: brand + sign out */}
      <div className="px-4 md:px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0', accentColor)}>
            <Key className="w-4 h-4 text-white" />
          </div>
          <div className="min-w-0">
            <h1 className="text-sm font-semibold text-gray-900 leading-tight">{title}</h1>
            <p className="text-xs text-gray-500 hidden sm:block">{subtitle}</p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 transition-colors flex-shrink-0"
        >
          <LogOut className="w-4 h-4" />
          <span className="hidden sm:inline">Sign out</span>
        </button>
      </div>

      {/* Nav tabs — scrollable on mobile */}
      <div className="flex overflow-x-auto px-4 md:px-6 scrollbar-none border-t border-gray-100">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== '/mcp-user/portal' && pathname.startsWith(href))
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-1.5 px-3 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition-colors flex-shrink-0',
                active
                  ? 'border-blue-600 text-blue-700'
                  : 'border-transparent text-gray-500 hover:text-gray-900'
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </Link>
          )
        })}
      </div>
    </header>
  )
}
