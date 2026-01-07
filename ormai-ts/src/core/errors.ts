/**
 * Error taxonomy for OrmAI.
 *
 * All errors extend OrmAIError and provide:
 * - A unique error code for programmatic handling
 * - Retry hints for LLM self-correction
 * - Structured details for debugging
 */

/**
 * Error codes for all OrmAI errors.
 */
export const ErrorCodes = {
  MODEL_NOT_ALLOWED: 'MODEL_NOT_ALLOWED',
  FIELD_NOT_ALLOWED: 'FIELD_NOT_ALLOWED',
  RELATION_NOT_ALLOWED: 'RELATION_NOT_ALLOWED',
  TENANT_SCOPE_REQUIRED: 'TENANT_SCOPE_REQUIRED',
  QUERY_TOO_BROAD: 'QUERY_TOO_BROAD',
  QUERY_BUDGET_EXCEEDED: 'QUERY_BUDGET_EXCEEDED',
  WRITE_DISABLED: 'WRITE_DISABLED',
  WRITE_APPROVAL_REQUIRED: 'WRITE_APPROVAL_REQUIRED',
  MAX_AFFECTED_ROWS_EXCEEDED: 'MAX_AFFECTED_ROWS_EXCEEDED',
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  NOT_FOUND: 'NOT_FOUND',
  ADAPTER_ERROR: 'ADAPTER_ERROR',
  INTERNAL_ERROR: 'INTERNAL_ERROR',
} as const;

export type ErrorCode = (typeof ErrorCodes)[keyof typeof ErrorCodes];

/**
 * Base error class for all OrmAI errors.
 */
export class OrmAIError extends Error {
  /** Unique error code for programmatic handling */
  readonly code: ErrorCode;

  /** Suggestions for LLM to retry with corrected input */
  readonly retryHints: readonly string[];

  /** Additional structured details */
  readonly details: Readonly<Record<string, unknown>>;

  constructor(
    code: ErrorCode,
    message: string,
    opts?: {
      retryHints?: string[];
      details?: Record<string, unknown>;
      cause?: Error;
    }
  ) {
    super(message, { cause: opts?.cause });
    this.name = this.constructor.name;
    this.code = code;
    this.retryHints = Object.freeze(opts?.retryHints ?? []);
    this.details = Object.freeze(opts?.details ?? {});

    // Maintain proper stack trace in V8
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, this.constructor);
    }
  }

  /**
   * Convert to a plain object for serialization.
   */
  toJSON(): Record<string, unknown> {
    return {
      name: this.name,
      code: this.code,
      message: this.message,
      retryHints: this.retryHints,
      details: this.details,
    };
  }
}

/**
 * Error thrown when a model is not in the policy allowlist.
 */
export class ModelNotAllowedError extends OrmAIError {
  constructor(model: string, allowedModels: string[]) {
    super(ErrorCodes.MODEL_NOT_ALLOWED, `Model '${model}' is not allowed.`, {
      retryHints: [
        `Use one of the allowed models: ${allowedModels.join(', ')}`,
        'Call db.describe_schema to see available models',
      ],
      details: { model, allowedModels },
    });
  }
}

/**
 * Error thrown when a field is not allowed by policy.
 */
export class FieldNotAllowedError extends OrmAIError {
  constructor(field: string, model: string, allowedFields: string[]) {
    super(ErrorCodes.FIELD_NOT_ALLOWED, `Field '${field}' on model '${model}' is not allowed.`, {
      retryHints: [
        `Use allowed fields: ${allowedFields.slice(0, 10).join(', ')}${allowedFields.length > 10 ? '...' : ''}`,
        `Call db.describe_schema to see available fields for ${model}`,
      ],
      details: { field, model, allowedFields },
    });
  }
}

/**
 * Error thrown when a relation is not allowed for expansion.
 */
export class RelationNotAllowedError extends OrmAIError {
  constructor(relation: string, model: string, allowedRelations: string[]) {
    super(
      ErrorCodes.RELATION_NOT_ALLOWED,
      `Relation '${relation}' on model '${model}' is not allowed.`,
      {
        retryHints: [
          allowedRelations.length > 0
            ? `Use allowed relations: ${allowedRelations.join(', ')}`
            : 'No relations are allowed for this model',
          `Call db.describe_schema to see available relations for ${model}`,
        ],
        details: { relation, model, allowedRelations },
      }
    );
  }
}

/**
 * Error thrown when tenant scoping is required but not present.
 */
export class TenantScopeRequiredError extends OrmAIError {
  constructor(model: string, scopeField: string) {
    super(
      ErrorCodes.TENANT_SCOPE_REQUIRED,
      `Tenant scoping is required for model '${model}'.`,
      {
        retryHints: [
          `Queries are automatically scoped to your tenant via '${scopeField}'`,
          'This filter is applied server-side and cannot be bypassed',
        ],
        details: { model, scopeField },
      }
    );
  }
}

/**
 * Error thrown when a query is too broad (e.g., no filters on large table).
 */
export class QueryTooBroadError extends OrmAIError {
  constructor(model: string, suggestion?: string) {
    super(
      ErrorCodes.QUERY_TOO_BROAD,
      `Query on model '${model}' is too broad. Add filters to narrow the results.`,
      {
        retryHints: [
          suggestion ?? 'Add a filter on an indexed field',
          'Consider filtering by date range, ID, or status',
          `Limit your query with 'take' parameter`,
        ],
        details: { model },
      }
    );
  }
}

/**
 * Error thrown when a query exceeds budget limits.
 */
export class QueryBudgetExceededError extends OrmAIError {
  constructor(
    budgetType: 'rows' | 'fields' | 'includes' | 'complexity' | 'timeout',
    limit: number,
    requested: number
  ) {
    const messages: Record<typeof budgetType, string> = {
      rows: `Requested ${requested} rows but maximum is ${limit}`,
      fields: `Selected ${requested} fields but maximum is ${limit}`,
      includes: `Include depth ${requested} exceeds maximum of ${limit}`,
      complexity: `Query complexity score ${requested} exceeds maximum of ${limit}`,
      timeout: `Query timeout ${requested}ms exceeds maximum of ${limit}ms`,
    };

    super(ErrorCodes.QUERY_BUDGET_EXCEEDED, messages[budgetType], {
      retryHints: [
        `Reduce your request to stay within the ${budgetType} limit of ${limit}`,
        budgetType === 'rows' ? `Use 'take' parameter to limit results` : undefined,
        budgetType === 'fields' ? 'Select fewer fields' : undefined,
        budgetType === 'includes' ? 'Reduce nesting depth of includes' : undefined,
      ].filter((h): h is string => h !== undefined),
      details: { budgetType, limit, requested },
    });
  }
}

/**
 * Error thrown when write operations are disabled.
 */
export class WriteDisabledError extends OrmAIError {
  constructor(operation: string, model: string) {
    super(
      ErrorCodes.WRITE_DISABLED,
      `Write operation '${operation}' is disabled for model '${model}'.`,
      {
        retryHints: [
          'Write operations must be explicitly enabled in the policy',
          'Contact an administrator to enable writes if needed',
        ],
        details: { operation, model },
      }
    );
  }
}

/**
 * Error thrown when a write operation requires approval.
 */
export class WriteApprovalRequiredError extends OrmAIError {
  constructor(operation: string, model: string, approvalId?: string) {
    super(
      ErrorCodes.WRITE_APPROVAL_REQUIRED,
      `Operation '${operation}' on model '${model}' requires approval.`,
      {
        retryHints: [
          'This operation has been queued for approval',
          approvalId
            ? `Approval ID: ${approvalId}`
            : 'An approval ID will be provided when the operation is queued',
        ],
        details: { operation, model, approvalId },
      }
    );
  }
}

/**
 * Error thrown when a mutation would affect too many rows.
 */
export class MaxAffectedRowsExceededError extends OrmAIError {
  constructor(operation: string, maxRows: number, affectedRows: number) {
    super(
      ErrorCodes.MAX_AFFECTED_ROWS_EXCEEDED,
      `Operation '${operation}' would affect ${affectedRows} rows, exceeding the maximum of ${maxRows}.`,
      {
        retryHints: [
          `Reduce the scope to affect at most ${maxRows} rows`,
          'Use more specific filters or provide explicit IDs',
          'Consider using bulk operations with explicit ID lists',
        ],
        details: { operation, maxRows, affectedRows },
      }
    );
  }
}

/**
 * Error thrown for validation failures.
 */
export class ValidationError extends OrmAIError {
  constructor(message: string, field?: string, details?: Record<string, unknown>) {
    super(ErrorCodes.VALIDATION_ERROR, message, {
      retryHints: [
        field ? `Check the value for field '${field}'` : 'Check your input values',
        'Ensure all required fields are provided',
      ],
      details: { field, ...details },
    });
  }
}

/**
 * Error thrown when a record is not found.
 *
 * Uses "safe not found" pattern - doesn't reveal if the record exists
 * but is filtered out by scoping.
 */
export class NotFoundError extends OrmAIError {
  constructor(model: string, id: string | number) {
    super(ErrorCodes.NOT_FOUND, `${model} with ID '${id}' not found.`, {
      retryHints: [
        'Verify the ID is correct',
        'The record may not exist or you may not have access to it',
      ],
      details: { model, id },
    });
  }
}

/**
 * Error thrown by ORM adapters for database-level errors.
 */
export class AdapterError extends OrmAIError {
  constructor(message: string, cause?: Error) {
    super(ErrorCodes.ADAPTER_ERROR, message, {
      retryHints: ['This may be a temporary database issue', 'Try again in a moment'],
      details: { originalError: cause?.message },
      cause,
    });
  }
}

/**
 * Error thrown when an adapter method is not implemented.
 */
export class AdapterNotImplementedError extends AdapterError {
  constructor(operation: string, adapterName: string) {
    super(`${operation} not implemented for ${adapterName} adapter`);
    this.name = 'AdapterNotImplementedError';
  }
}

/**
 * Error thrown for internal/unexpected errors.
 */
export class InternalError extends OrmAIError {
  constructor(message: string, cause?: Error) {
    super(ErrorCodes.INTERNAL_ERROR, message, {
      retryHints: ['An unexpected error occurred', 'Please try again'],
      details: { originalError: cause?.message },
      cause,
    });
  }
}

/**
 * Type guard to check if an error is an OrmAIError.
 */
export function isOrmAIError(error: unknown): error is OrmAIError {
  return error instanceof OrmAIError;
}

/**
 * Wrap an unknown error as an OrmAIError.
 */
export function wrapError(error: unknown): OrmAIError {
  if (isOrmAIError(error)) {
    return error;
  }
  if (error instanceof Error) {
    return new InternalError(error.message, error);
  }
  return new InternalError(String(error));
}
