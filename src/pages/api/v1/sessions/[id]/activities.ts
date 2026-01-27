import type { APIContext } from 'astro';
import { authenticateAny, errorResponse, successResponse } from '@lib/auth/middleware';
import { getSessionWithDetails, getSessionActivities } from '@lib/db/queries';

export async function GET(context: APIContext) {
  const { request, params } = context;
  const sessionId = params.id as string;
  const db = context.locals.runtime.env.DB;

  // Authenticate (supports both web session and API tokens)
  const authResult = await authenticateAny(request, db);
  if (!authResult.success) {
    return errorResponse(authResult.error, authResult.status);
  }
  const { team } = authResult.context;

  // Parse query params
  const url = new URL(request.url);
  const limitParam = url.searchParams.get('limit');
  const offsetParam = url.searchParams.get('offset');
  const rawLimit = limitParam ? parseInt(limitParam, 10) : 50;
  const limit = Number.isNaN(rawLimit) ? 50 : Math.min(Math.max(rawLimit, 1), 100);
  const rawOffset = offsetParam ? parseInt(offsetParam, 10) : 0;
  const offset = Number.isNaN(rawOffset) || rawOffset < 0 ? 0 : rawOffset;

  try {
    // Verify session exists and belongs to this team
    const session = await getSessionWithDetails(db, sessionId, team.id);
    if (!session) {
      return errorResponse('Session not found', 404);
    }

    const result = await getSessionActivities(db, sessionId, { limit, offset });

    return successResponse({
      session: {
        id: session.id,
        user: session.user,
        device: {
          id: session.device.id,
          name: session.device.name,
          is_remote: session.device.is_remote === 1,
        },
        repo: session.repo,
        branch: session.branch,
        worktree: session.worktree,
        status: session.status,
        started_at: session.started_at,
        last_activity_at: session.last_activity_at,
        ended_at: session.ended_at,
      },
      activities: result.activities,
      total: result.total,
      hasMore: result.hasMore,
    });
  } catch (error) {
    console.error('Session activities error:', error);
    return errorResponse('Failed to fetch session activities', 500);
  }
}
