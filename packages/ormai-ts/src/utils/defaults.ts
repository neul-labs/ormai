/**
 * Default profiles for common deployment scenarios.
 */

import { z } from 'zod';
import type { Budget, WritePolicy } from '../policy/models.js';

/**
 * Profile mode for different deployment scenarios.
 */
export type ProfileMode = 'prod' | 'internal' | 'dev';

/**
 * Defaults profile configuration.
 */
export const DefaultsProfileSchema = z
  .object({
    mode: z.enum(['prod', 'internal', 'dev']),
    maxRows: z.number().int().min(1).default(100),
    maxIncludesDepth: z.number().int().min(0).default(1),
    maxSelectFields: z.number().int().min(1).default(40),
    statementTimeoutMs: z.number().int().min(100).default(2000),
    writesEnabled: z.boolean().default(false),
    requireTenantScope: z.boolean().default(true),
    requireReasonForWrites: z.boolean().default(true),
  })
  .readonly();

export type DefaultsProfile = z.infer<typeof DefaultsProfileSchema>;

/**
 * Production defaults - most restrictive.
 */
export const PROD_DEFAULTS: DefaultsProfile = {
  mode: 'prod',
  maxRows: 100,
  maxIncludesDepth: 1,
  maxSelectFields: 40,
  statementTimeoutMs: 2000,
  writesEnabled: false,
  requireTenantScope: true,
  requireReasonForWrites: true,
};

/**
 * Internal/admin defaults - more permissive.
 */
export const INTERNAL_DEFAULTS: DefaultsProfile = {
  mode: 'internal',
  maxRows: 500,
  maxIncludesDepth: 2,
  maxSelectFields: 100,
  statementTimeoutMs: 5000,
  writesEnabled: false,
  requireTenantScope: true,
  requireReasonForWrites: true,
};

/**
 * Development defaults - most permissive.
 */
export const DEV_DEFAULTS: DefaultsProfile = {
  mode: 'dev',
  maxRows: 1000,
  maxIncludesDepth: 3,
  maxSelectFields: 200,
  statementTimeoutMs: 10000,
  writesEnabled: true,
  requireTenantScope: false,
  requireReasonForWrites: false,
};

/**
 * Get defaults profile by mode.
 */
export function getDefaultsProfile(mode: ProfileMode): DefaultsProfile {
  switch (mode) {
    case 'prod':
      return PROD_DEFAULTS;
    case 'internal':
      return INTERNAL_DEFAULTS;
    case 'dev':
      return DEV_DEFAULTS;
  }
}

/**
 * Create a budget from a defaults profile.
 */
export function budgetFromProfile(profile: DefaultsProfile): Budget {
  return {
    maxRows: profile.maxRows,
    maxIncludesDepth: profile.maxIncludesDepth,
    maxSelectFields: profile.maxSelectFields,
    statementTimeoutMs: profile.statementTimeoutMs,
    maxComplexityScore: 100,
    broadQueryGuard: profile.mode === 'prod',
    minFiltersForBroadQuery: profile.mode === 'prod' ? 1 : 0,
  };
}

/**
 * Create a write policy from a defaults profile.
 */
export function writePolicyFromProfile(profile: DefaultsProfile): WritePolicy {
  return {
    enabled: profile.writesEnabled,
    allowCreate: profile.writesEnabled,
    allowUpdate: profile.writesEnabled,
    allowDelete: profile.writesEnabled,
    allowBulk: profile.writesEnabled && profile.mode !== 'prod',
    requirePrimaryKey: true,
    softDelete: true,
    maxAffectedRows: profile.mode === 'prod' ? 1 : 100,
    requireReason: profile.requireReasonForWrites,
    requireApproval: false,
    readonlyFields: [],
  };
}
