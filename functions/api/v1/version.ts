/**
 * Version endpoint for update checking.
 */

import { successResponse } from '@lib/auth/middleware';

// This should match package.json version
const VERSION = '0.1.0';
const REPO = 'overlapcode/overlap';

type Env = Record<string, never>;

export const onRequestGet: PagesFunction<Env> = async () => {
  return successResponse({
    version: VERSION,
    repository: `https://github.com/${REPO}`,
    releases: `https://github.com/${REPO}/releases`,
    latest_check: `https://api.github.com/repos/${REPO}/releases/latest`,
  });
};
