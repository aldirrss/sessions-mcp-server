import { z } from 'zod'

export const LoginSchema = z.object({
  username: z.string().min(1).max(100),
  password: z.string().min(1).max(200),
})

export const RegisterSchema = z.object({
  username: z.string().min(3).max(50).regex(/^[a-z0-9_-]+$/, 'lowercase letters, numbers, _ and - only'),
  email: z.email(),
  password: z.string().min(8).max(200),
})

export const CreateTokenSchema = z.object({
  name: z.string().min(1).max(100),
  expires_days: z.number().int().min(1).max(3650).nullable().optional(),
})

export const PatchUserSchema = z.object({
  role: z.enum(['user', 'admin']).optional(),
  is_active: z.boolean().optional(),
}).refine(data => data.role !== undefined || data.is_active !== undefined, {
  message: 'At least one of role or is_active must be provided',
})
