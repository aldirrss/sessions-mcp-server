import postgres from 'postgres'

declare global {
  // eslint-disable-next-line no-var
  var _sql: ReturnType<typeof postgres> | undefined
}

const sql = global._sql ?? postgres(process.env.DATABASE_URL!, {
  max: 5,
  idle_timeout: 20,
  connect_timeout: 10,
})

if (process.env.NODE_ENV !== 'production') global._sql = sql

export default sql
