import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'MCP Portal',
  description: 'User portal for managing sessions, skills, and tokens',
}

export default function UserLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
