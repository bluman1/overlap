import { z } from 'zod';
import { errorResponse, successResponse } from '@lib/auth/middleware';
import { getTeam, createTeam, createUser } from '@lib/db/queries';
import { generateId, generateToken } from '@lib/utils/id';
import { hashPassword } from '@lib/utils/crypto';
import { ensureMigrated } from '@lib/db/migrate';

const SetupSchema = z.object({
  team_name: z.string().min(1).max(100),
  admin_name: z.string().min(1).max(100),
  admin_email: z.string().email().nullable().optional(),
  dashboard_password: z.string().min(8),
});

type Env = {
  DB: D1Database;
};

// GET: Check setup status and ensure database is migrated
export const onRequestGet: PagesFunction<Env> = async (context) => {
  const { env } = context;

  // Auto-migrate database
  await ensureMigrated(env.DB);

  // Check if team already exists
  const existingTeam = await getTeam(env.DB);

  return successResponse({
    initialized: !!existingTeam,
    team_name: existingTeam?.name ?? null,
  });
};

// POST: Create team
export const onRequestPost: PagesFunction<Env> = async (context) => {
  const { request, env } = context;

  // Auto-migrate database on first setup
  await ensureMigrated(env.DB);

  // Check if team already exists
  const existingTeam = await getTeam(env.DB);
  if (existingTeam) {
    return errorResponse('Team already configured', 400);
  }

  // Parse body
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return errorResponse('Invalid JSON body', 400);
  }

  const parseResult = SetupSchema.safeParse(body);
  if (!parseResult.success) {
    return errorResponse(`Validation error: ${parseResult.error.message}`, 400);
  }

  const input = parseResult.data;

  try {
    // Generate tokens
    const teamId = generateId();
    const teamToken = generateToken();
    const userId = generateId();
    const userToken = generateToken();

    // Hash password
    const passwordHash = await hashPassword(input.dashboard_password);

    // Create team
    await createTeam(env.DB, {
      id: teamId,
      name: input.team_name,
      team_token: teamToken,
      dashboard_password_hash: passwordHash,
    });

    // Create admin user
    await createUser(env.DB, {
      id: userId,
      team_id: teamId,
      user_token: userToken,
      name: input.admin_name,
      email: input.admin_email ?? null,
      role: 'admin',
    });

    return successResponse({
      team_id: teamId,
      team_token: teamToken,
      user_id: userId,
      user_token: userToken,
      message: 'Team created successfully',
    }, 201);
  } catch (error) {
    console.error('Setup error:', error);
    return errorResponse('Failed to create team', 500);
  }
};
