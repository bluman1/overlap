import type { APIContext } from 'astro';
import { authenticateAny, errorResponse, successResponse } from '@lib/auth/middleware';
import { getTeamRepos, getUserRepos } from '@lib/db/queries';

export async function GET(context: APIContext) {
  const { request } = context;
  const db = context.locals.runtime.env.DB;

  // Authenticate (supports both web session and API tokens)
  const authResult = await authenticateAny(request, db);
  if (!authResult.success) {
    return errorResponse(authResult.error, authResult.status);
  }

  const { team, user } = authResult.context;
  const isAdmin = user.role === 'admin';

  try {
    // Admins see all team repos, non-admins only see repos they've worked on
    const repos = isAdmin
      ? await getTeamRepos(db, team.id)
      : await getUserRepos(db, team.id, user.id);

    return successResponse({
      repos: repos.map((repo) => ({
        id: repo.id,
        name: repo.name,
        remote_url: repo.remote_url,
        is_public: repo.is_public === 1,
        created_at: repo.created_at,
      })),
      is_admin: isAdmin,
    });
  } catch (error) {
    console.error('List repos error:', error);
    return errorResponse('Failed to list repos', 500);
  }
}
