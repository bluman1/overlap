import type { APIContext } from 'astro';
import { authenticateAny, isAdmin, errorResponse, successResponse } from '@lib/auth/middleware';
import { getTeamUsers } from '@lib/db/queries';

// GET: List team members (accessible by all authenticated users)
export async function GET(context: APIContext) {
  const { request } = context;
  const db = context.locals.runtime.env.DB;

  // Authenticate (supports both web session and API tokens)
  const authResult = await authenticateAny(request, db);
  if (!authResult.success) {
    return errorResponse(authResult.error, authResult.status);
  }

  const { team } = authResult.context;

  try {
    const users = await getTeamUsers(db, team.id);

    return successResponse({
      users: users.map((user) => ({
        id: user.id,
        name: user.name,
        email: user.email,
        role: user.role,
        is_active: user.is_active === 1,
        stale_timeout_hours: user.stale_timeout_hours,
        created_at: user.created_at,
      })),
      is_admin: isAdmin(authResult.context),
      current_user_id: authResult.context.user.id,
    });
  } catch (error) {
    console.error('List users error:', error);
    return errorResponse('Failed to list users', 500);
  }
}
