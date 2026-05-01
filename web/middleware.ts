import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { getIronSession } from 'iron-session'
import { sessionOptions, SessionData } from '@/lib/auth'

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // API auth routes — always public
  if (pathname.startsWith('/api/auth/')) return NextResponse.next()

  // Public pages — no session required
  if (
    pathname.startsWith('/mcp-admin/login') ||
    pathname.startsWith('/mcp-user/login') ||
    pathname.startsWith('/mcp-user/register')
  ) {
    return NextResponse.next()
  }

  const res = NextResponse.next()
  const session = await getIronSession<SessionData>(request, res, sessionOptions)

  // User portal — require userId
  if (pathname.startsWith('/mcp-user/')) {
    if (!session.userId) {
      const url = request.nextUrl.clone()
      url.pathname = '/mcp-user/login'
      return NextResponse.redirect(url)
    }
    return res
  }

  // Admin panel — require isAdmin
  if (pathname.startsWith('/mcp-admin/')) {
    if (!session.isAdmin) {
      const url = request.nextUrl.clone()
      url.pathname = '/mcp-admin/login'
      return NextResponse.redirect(url)
    }
    return res
  }

  return res
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
