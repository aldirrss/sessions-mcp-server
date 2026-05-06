'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { LayoutDashboard, MessageSquare, BookOpen, Settings2, Users, LogOut, Menu, X, ShieldBan } from 'lucide-react'
import { cn } from '@/lib/cn'

const navItems = [
  { href: '/mcp-admin', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { href: '/mcp-admin/sessions', label: 'Sessions', icon: MessageSquare },
  { href: '/mcp-admin/skills', label: 'Skills', icon: BookOpen },
  { href: '/mcp-admin/config', label: 'Config', icon: Settings2 },
  { href: '/mcp-admin/users', label: 'Users', icon: Users },
  { href: '/mcp-admin/blacklist', label: 'Blacklist', icon: ShieldBan },
]

export default function NavSidebar() {
  const pathname = usePathname()
  const [open, setOpen] = useState(false)

  async function handleLogout() {
    await fetch('/panel/api/auth/logout', { method: 'POST' })
    window.location.href = '/panel/mcp-admin/login'
  }

  const sidebarContent = (
    <>
      <div className="px-5 py-5 border-b border-gray-100 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">MCP Admin</p>
          <p className="text-sm font-semibold text-gray-900 mt-0.5">Sessions MCP Server</p>
        </div>
        <button onClick={() => setOpen(false)} className="md:hidden p-1 rounded-lg text-gray-400 hover:text-gray-600">
          <X className="w-5 h-5" />
        </button>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {navItems.map(({ href, label, icon: Icon, exact }) => {
          const active = exact ? pathname === href : pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              onClick={() => setOpen(false)}
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
    </>
  )

  return (
    <>
      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-20 bg-white border-b border-gray-200 flex items-center gap-3 px-4 py-3">
        <button onClick={() => setOpen(true)} className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100">
          <Menu className="w-5 h-5" />
        </button>
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider leading-none">MCP Admin</p>
          <p className="text-sm font-semibold text-gray-900">Sessions MCP Server</p>
        </div>
      </div>

      {/* Mobile backdrop */}
      {open && (
        <div
          className="md:hidden fixed inset-0 z-30 bg-black/40"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Sidebar — always visible on desktop, slide-in on mobile */}
      <aside className={cn(
        'fixed inset-y-0 left-0 w-60 bg-white border-r border-gray-200 flex flex-col z-40 transition-transform duration-200',
        'md:translate-x-0',
        open ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
      )}>
        {sidebarContent}
      </aside>
    </>
  )
}
