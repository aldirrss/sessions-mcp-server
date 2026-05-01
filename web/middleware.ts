import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { getIronSession } from 'iron-session'
import { sessionOptions, SessionData } from '@/lib/auth'

const ADMIN_PATHS = ['/dashboard', '/sessions', '/skills', '/config', '/users']
const PORTAL_PATHS = ['/portal']
const PUBLIC_PATHS = ['/login', '/register', '/user-login']

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // API auth routes — always public
  if (pathname.startsWith('/api/auth/')) return NextResponse.next()

  // Static public pages
  if (PUBLIC_PATHS.some(p => pathname === p || pathname.startsWith(p + '/'))) {
    return NextResponse.next()
  }

  const res = NextResponse.next()
  const session = await getIronSession<SessionData>(request, res, sessionOptions)

  // Portal routes — require user session (userId present)
  if (PORTAL_PATHS.some(p => pathname === p || pathname.startsWith(p + '/'))) {
    if (!session.userId) {
      const url = request.nextUrl.clone()
      url.pathname = '/user-login'
      return NextResponse.redirect(url)
    }
    return res
  }

  // Admin routes — require isAdmin flag
  const isAdminPath = pathname === '/' || ADMIN_PATHS.some(p => pathname === p || pathname.startsWith(p + '/'))
  if (isAdminPath) {
    if (!session.isAdmin) {
      const url = request.nextUrl.clone()
      url.pathname = '/login'
      return NextResponse.redirect(url)
    }
    return res
  }

  return res
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
