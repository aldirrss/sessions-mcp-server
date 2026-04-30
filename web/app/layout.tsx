import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'LM MCP Admin',
  description: 'Admin panel for managing MCP sessions and skills',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
