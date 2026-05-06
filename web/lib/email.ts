import nodemailer from 'nodemailer'

function createTransport() {
  return nodemailer.createTransport({
    host: process.env.SMTP_HOST ?? 'localhost',
    port: Number(process.env.SMTP_PORT ?? 587),
    secure: process.env.SMTP_SECURE === 'true',
    auth: process.env.SMTP_USER
      ? { user: process.env.SMTP_USER, pass: process.env.SMTP_PASS }
      : undefined,
  })
}

const FROM = process.env.SMTP_FROM ?? 'noreply@mcp.local'
const ADMIN_EMAIL = process.env.ADMIN_EMAIL ?? ''

export async function sendAdminTeamRequest(opts: {
  requesterUsername: string
  requesterEmail: string
  teamName: string
  reason: string
  requestId: string
}) {
  if (!ADMIN_EMAIL) return
  await createTransport().sendMail({
    from: FROM,
    to: ADMIN_EMAIL,
    subject: `[Sessions MCP] New team request: ${opts.teamName}`,
    text: [
      `User ${opts.requesterUsername} (${opts.requesterEmail}) has requested a new team.`,
      ``,
      `Team name : ${opts.teamName}`,
      `Reason    : ${opts.reason || '(none)'}`,
      ``,
      `Review this request in the admin panel → Users → Team Requests.`,
      `Request ID: ${opts.requestId}`,
    ].join('\n'),
  })
}

export async function sendUserTeamApproved(opts: {
  toEmail: string
  username: string
  teamName: string
}) {
  await createTransport().sendMail({
    from: FROM,
    to: opts.toEmail,
    subject: `[Sessions MCP] Your team "${opts.teamName}" has been approved`,
    text: [
      `Hi ${opts.username},`,
      ``,
      `Your request to create team "${opts.teamName}" has been approved.`,
      `You can now manage your team from the portal.`,
    ].join('\n'),
  })
}

export async function sendUserEmailBlacklisted(opts: {
  toEmail: string
  reason?: string
}) {
  await createTransport().sendMail({
    from: FROM,
    to: opts.toEmail,
    subject: `[Sessions MCP] Your email has been blocked`,
    text: [
      `Your email address (${opts.toEmail}) has been blocked from registering on Sessions MCP Server.`,
      opts.reason ? `\nReason: ${opts.reason}` : '',
      `\nIf you believe this is a mistake, please contact the administrator.`,
    ].join('\n'),
  })
}
