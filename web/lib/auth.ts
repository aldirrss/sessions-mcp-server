import { SessionOptions } from 'iron-session'

export interface SessionData {
  // Admin web panel
  isAdmin?: boolean
  // Regular user portal
  userId?: string
  username?: string
  email?: string
  role?: 'user' | 'admin'
}

export const sessionOptions: SessionOptions = {
  password: process.env.SESSION_SECRET!,
  cookieName: 'lm-session',
  cookieOptions: {
    secure: process.env.NODE_ENV === 'production',
    maxAge: 60 * 60 * 8,
  },
}
