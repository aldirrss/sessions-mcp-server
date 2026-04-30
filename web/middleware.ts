import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { getIronSession } from 'iron-session'
import { sessionOptions, SessionData } from '@/lib/auth'

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  const isAuthPath = pathname === '/login' || pathname.startsWith('/api/auth/')
  if (isAuthPath) return NextResponse.next()

  const res = NextResponse.next()
  const session = await getIronSession<SessionData>(request, res, sessionOptions)

  if (!session.isAdmin) {
    const loginUrl = request.nextUrl.clone()
    loginUrl.pathname = '/panel/mcp-admin/login'
    return NextResponse.redirect(loginUrl)
  }

  return res
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
