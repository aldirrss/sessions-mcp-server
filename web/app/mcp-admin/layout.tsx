import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'LM MCP Admin',
  description: 'Admin panel for managing MCP sessions, skills, and users',
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
