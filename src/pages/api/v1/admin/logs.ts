import type { APIContext } from 'astro';
import { authenticateAny, requireAdmin, errorResponse, successResponse } from '@lib/auth/middleware';
import { getPluginLogs, getTeamUsers, deleteOldPluginLogs } from '@lib/db/queries';

/**
 * GET /api/v1/admin/logs
 * Get plugin logs for the team (admin only).
 *
 * Query params:
 * - user_id: Filter by user ID
 * - level: Filter by log level (DEBUG, INFO, WARN, ERROR)
 * - limit: Max results (default 100, max 500)
 * - offset: Pagination offset
 */
export async function GET(context: APIContext) {
  const { request } = context;
  const db = context.locals.runtime.env.DB;

  // Authenticate and check admin role
  const authResult = await authenticateAny(request, db);
  if (!authResult.success) {
    return errorResponse(authResult.error, authResult.status);
  }

  const adminCheck = requireAdmin(authResult.context);
  if (!adminCheck.success) {
    return errorResponse(adminCheck.error, adminCheck.status);
  }

  const { team } = authResult.context;

  // Parse query params
  const url = new URL(request.url);
  const userId = url.searchParams.get('user_id') || undefined;
  const level = url.searchParams.get('level') || undefined;
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '100', 10), 500);
  const offset = parseInt(url.searchParams.get('offset') || '0', 10);

  try {
    // Get logs
    const { logs, total } = await getPluginLogs(db, team.id, {
      userId,
      level,
      limit,
      offset,
    });

    // Get team users for filtering dropdown
    const users = await getTeamUsers(db, team.id);

    return successResponse({
      logs,
      total,
      limit,
      offset,
      hasMore: offset + logs.length < total,
      users: users.map((u) => ({ id: u.id, name: u.name })),
    });
  } catch (error) {
    console.error('Failed to fetch logs:', error);
    return errorResponse('Failed to fetch logs', 500);
  }
}

/**
 * DELETE /api/v1/admin/logs
 * Delete old logs (admin only).
 *
 * Query params:
 * - days: Delete logs older than this many days (default 30)
 */
export async function DELETE(context: APIContext) {
  const { request } = context;
  const db = context.locals.runtime.env.DB;

  // Authenticate and check admin role
  const authResult = await authenticateAny(request, db);
  if (!authResult.success) {
    return errorResponse(authResult.error, authResult.status);
  }

  const adminCheck = requireAdmin(authResult.context);
  if (!adminCheck.success) {
    return errorResponse(adminCheck.error, adminCheck.status);
  }

  // Parse query params
  const url = new URL(request.url);
  const days = parseInt(url.searchParams.get('days') || '30', 10);

  if (days < 1 || days > 365) {
    return errorResponse('Days must be between 1 and 365', 400);
  }

  try {
    const deleted = await deleteOldPluginLogs(db, days);
    return successResponse({ deleted, days });
  } catch (error) {
    console.error('Failed to delete logs:', error);
    return errorResponse('Failed to delete logs', 500);
  }
}
