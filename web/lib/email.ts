import nodemailer from 'nodemailer'

function createTransport() {
  const port = Number(process.env.SMTP_PORT ?? 587)
  // Port 465 = SSL (secure: true). Port 587/25 = STARTTLS (secure: false).
  // SMTP_SECURE env only overrides this when explicitly set to 'true' AND port is 465.
  const secure = process.env.SMTP_SECURE === 'true' && port === 465
  return nodemailer.createTransport({
    host: process.env.SMTP_HOST ?? 'localhost',
    port,
    secure,
    auth: process.env.SMTP_USER
      ? { user: process.env.SMTP_USER, pass: process.env.SMTP_PASS }
      : undefined,
  })
}

// Fall back to SMTP_USER so Zoho doesn't reject mismatched sender
const FROM = process.env.SMTP_FROM ?? process.env.SMTP_USER ?? 'noreply@mcp.local'
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

export async function sendUserTeamRejected(opts: {
  toEmail: string
  username: string
  teamName: string
}) {
  await createTransport().sendMail({
    from: FROM,
    to: opts.toEmail,
    subject: `[Sessions MCP] Your team request "${opts.teamName}" was not approved`,
    text: [
      `Hi ${opts.username},`,
      ``,
      `Unfortunately, your request to create team "${opts.teamName}" has been rejected.`,
      `If you think this was a mistake, please contact the administrator.`,
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
