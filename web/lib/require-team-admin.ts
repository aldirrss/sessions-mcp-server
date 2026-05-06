import { cookies } from 'next/headers'
import { getIronSession } from 'iron-session'
import { sessionOptions } from '@/lib/auth'
import type { SessionData } from '@/lib/auth'
import { NextResponse } from 'next/server'
import sql from '@/lib/db'

export async function requireTeamAdmin(
  teamId: string
): Promise<{ userId: string } | { error: NextResponse }> {
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) {
    return { error: NextResponse.json({ error: 'Unauthorized' }, { status: 401 }) }
  }
  const [member] = await sql`
    SELECT role FROM team_members WHERE team_id = ${teamId}::uuid AND user_id = ${session.userId}::uuid
  `
  if (!member || member.role !== 'admin') {
    return { error: NextResponse.json({ error: 'Forbidden' }, { status: 403 }) }
  }
  return { userId: session.userId }
}

export async function requireTeamMember(
  teamId: string
): Promise<{ userId: string; role: string } | { error: NextResponse }> {
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) {
    return { error: NextResponse.json({ error: 'Unauthorized' }, { status: 401 }) }
  }
  const [member] = await sql`
    SELECT role FROM team_members WHERE team_id = ${teamId}::uuid AND user_id = ${session.userId}::uuid
  `
  if (!member) {
    return { error: NextResponse.json({ error: 'Forbidden' }, { status: 403 }) }
  }
  return { userId: session.userId, role: member.role }
}
