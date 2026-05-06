import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'LM MCP',
  description: 'Sessions MCP Server',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
