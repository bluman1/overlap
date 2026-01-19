import type { APIContext } from 'astro';
import { z } from 'zod';
import { authenticateRequest, errorResponse, successResponse } from '@lib/auth/middleware';
import { createPluginLogsBatch } from '@lib/db/queries';
import { generateId } from '@lib/utils/id';

// Schema for a single log entry
const LogEntrySchema = z.object({
  level: z.enum(['DEBUG', 'INFO', 'WARN', 'ERROR']),
  hook: z.string().nullable().optional(),
  session_id: z.string().nullable().optional(),
  message: z.string(),
  data: z.record(z.unknown()).nullable().optional(),
  error: z.object({
    type: z.string(),
    message: z.string(),
    traceback: z.string().optional(),
  }).nullable().optional(),
  timestamp: z.string().optional(), // ISO timestamp from plugin
});

// Schema for batch log submission
const LogsSchema = z.object({
  logs: z.array(LogEntrySchema).max(100), // Max 100 logs per request
});

/**
 * POST /api/v1/logs
 * Receive logs from the plugin and store them in the database.
 */
export async function POST(context: APIContext) {
  const { request } = context;
  const db = context.locals.runtime.env.DB;

  // Authenticate
  const authResult = await authenticateRequest(request, db);
  if (!authResult.success) {
    return errorResponse(authResult.error, authResult.status);
  }
  const { user } = authResult.context;

  // Parse body
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return errorResponse('Invalid JSON body', 400);
  }

  const parseResult = LogsSchema.safeParse(body);
  if (!parseResult.success) {
    return errorResponse(`Validation error: ${parseResult.error.message}`, 400);
  }

  const { logs } = parseResult.data;

  if (logs.length === 0) {
    return successResponse({ received: 0 });
  }

  try {
    // Transform logs for database
    const dbLogs = logs.map((log) => ({
      id: generateId(),
      user_id: user.id,
      level: log.level,
      hook: log.hook ?? null,
      session_id: log.session_id ?? null,
      message: log.message,
      data: log.data ? JSON.stringify(log.data) : null,
      error: log.error ? JSON.stringify(log.error) : null,
    }));

    // Batch insert
    await createPluginLogsBatch(db, dbLogs);

    return successResponse({ received: logs.length });
  } catch (error) {
    console.error('Failed to store logs:', error);
    return errorResponse('Failed to store logs', 500);
  }
}
