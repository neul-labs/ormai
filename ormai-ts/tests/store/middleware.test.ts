/**
 * Tests for audit middleware (withAudit, redaction, createAuditedToolRegistry).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { z } from 'zod';
import { withAudit, createAuditedToolRegistry } from '../../src/store/middleware.js';
import type { AuditMiddlewareOptions } from '../../src/store/middleware.js';
import type { AuditStore } from '../../src/store/base.js';
import type { AuditRecord } from '../../src/store/models.js';
import type { Tool } from '../../src/tools/base.js';
import { OrmAIError, ErrorCodes } from '../../src/core/errors.js';
import { createPrincipal } from '../../src/core/context.js';
import type { RunContext } from '../../src/core/context.js';

function makeContext(): RunContext {
  return {
    principal: createPrincipal({
      tenantId: 'tenant-1',
      userId: 'user-1',
      roles: ['admin'],
    }),
    db: {},
    requestId: 'req-001',
    traceId: 'trace-001',
    now: new Date(),
  };
}

function makeTool<Input, Output>(
  name: string,
  execute: (input: Input, ctx: RunContext) => Promise<Output>
): Tool<Input, Output> {
  return {
    name,
    description: `Tool: ${name}`,
    inputSchema: z.object({}).passthrough(),
    execute,
  };
}

describe('withAudit', () => {
  let store: AuditStore;
  let storedRecords: AuditRecord[];
  let ctx: RunContext;

  beforeEach(() => {
    storedRecords = [];
    store = {
      store: vi.fn(async (record: AuditRecord) => {
        storedRecords.push(record);
      }),
      get: vi.fn(),
      query: vi.fn(),
    };
    ctx = makeContext();
  });

  it('should wrap a tool and store an audit record on success', async () => {
    const tool = makeTool('test_tool', async () => 'ok');
    const audited = withAudit(tool, { store });

    const result = await audited.execute({}, ctx);
    expect(result).toBe('ok');
    expect(storedRecords.length).toBe(1);
    expect(storedRecords[0].toolName).toBe('test_tool');
    expect(storedRecords[0].principalId).toBe('user-1');
    expect(storedRecords[0].tenantId).toBe('tenant-1');
    expect(storedRecords[0].requestId).toBe('req-001');
    expect(storedRecords[0].traceId).toBe('trace-001');
    expect(storedRecords[0].error).toBeUndefined();
  });

  it('should include durationMs in audit record', async () => {
    const tool = makeTool('slow_tool', async () => {
      await new Promise((r) => setTimeout(r, 10));
      return 'done';
    });
    const audited = withAudit(tool, { store });

    await audited.execute({}, ctx);
    expect(storedRecords[0].durationMs).toBeGreaterThanOrEqual(0);
  });

  it('should store an audit record with error when tool throws OrmAIError', async () => {
    const tool = makeTool('failing_tool', async () => {
      throw new OrmAIError(ErrorCodes.VALIDATION_ERROR, 'bad input', {
        details: { field: 'email' },
      });
    });
    const audited = withAudit(tool, { store });

    await expect(audited.execute({}, ctx)).rejects.toThrow(OrmAIError);
    expect(storedRecords.length).toBe(1);
    expect(storedRecords[0].error).toBeDefined();
    expect(storedRecords[0].error!.type).toBe('OrmAIError');
    expect(storedRecords[0].error!.message).toBe('bad input');
    expect(storedRecords[0].error!.code).toBe('VALIDATION_ERROR');
  });

  it('should store an audit record with error when tool throws a plain Error', async () => {
    const tool = makeTool('crash_tool', async () => {
      throw new Error('unexpected');
    });
    const audited = withAudit(tool, { store });

    await expect(audited.execute({}, ctx)).rejects.toThrow('unexpected');
    expect(storedRecords.length).toBe(1);
    expect(storedRecords[0].error).toBeDefined();
    expect(storedRecords[0].error!.type).toBe('Error');
    expect(storedRecords[0].error!.message).toBe('unexpected');
  });

  it('should store an audit record with error when tool throws a non-Error', async () => {
    const tool = makeTool('weird_tool', async () => {
      throw 'string error';
    });
    const audited = withAudit(tool, { store });

    await expect(audited.execute({}, ctx)).rejects.toBe('string error');
    expect(storedRecords.length).toBe(1);
    expect(storedRecords[0].error!.type).toBe('Error');
    expect(storedRecords[0].error!.message).toBe('string error');
  });

  it('should preserve tool name, description, and inputSchema', () => {
    const schema = z.object({ name: z.string() });
    const tool: Tool<{ name: string }, string> = {
      name: 'my_tool',
      description: 'A test tool',
      inputSchema: schema,
      execute: async () => 'ok',
    };
    const audited = withAudit(tool, { store });
    expect(audited.name).toBe('my_tool');
    expect(audited.description).toBe('A test tool');
    expect(audited.inputSchema).toBe(schema);
  });

  describe('includeInputs', () => {
    it('should include inputs by default', async () => {
      const tool = makeTool('tool', async () => 'ok');
      const audited = withAudit(tool, { store });

      await audited.execute({ sql: 'SELECT 1' }, ctx);
      expect(storedRecords[0].inputs).toEqual({ sql: 'SELECT 1' });
    });

    it('should exclude inputs when includeInputs is false', async () => {
      const tool = makeTool('tool', async () => 'ok');
      const audited = withAudit(tool, { store, includeInputs: false });

      await audited.execute({ sql: 'SELECT 1' }, ctx);
      expect(storedRecords[0].inputs).toEqual({});
    });
  });

  describe('includeOutputs', () => {
    it('should exclude outputs by default', async () => {
      const tool = makeTool('tool', async () => ({ data: 'secret' }));
      const audited = withAudit(tool, { store });

      await audited.execute({}, ctx);
      expect(storedRecords[0].outputs).toBeUndefined();
    });

    it('should include outputs when includeOutputs is true', async () => {
      const tool = makeTool('tool', async () => ({ data: 'visible' }));
      const audited = withAudit(tool, { store, includeOutputs: true });

      await audited.execute({}, ctx);
      expect(storedRecords[0].outputs).toEqual({ data: 'visible' });
    });
  });

  describe('redaction', () => {
    it('should redact specified input fields', async () => {
      const tool = makeTool('tool', async () => 'ok');
      const audited = withAudit(tool, {
        store,
        redactInputFields: ['password', 'token'],
      });

      await audited.execute(
        { username: 'alice', password: 'secret', token: 'abc123' },
        ctx
      );
      expect(storedRecords[0].inputs.password).toBe('[REDACTED]');
      expect(storedRecords[0].inputs.token).toBe('[REDACTED]');
      expect(storedRecords[0].inputs.username).toBe('alice');
    });

    it('should redact specified output fields', async () => {
      const tool = makeTool('tool', async () => ({
        name: 'alice',
        ssn: '123-45-6789',
      }));
      const audited = withAudit(tool, {
        store,
        includeOutputs: true,
        redactOutputFields: ['ssn'],
      });

      await audited.execute({}, ctx);
      expect(storedRecords[0].outputs!.ssn).toBe('[REDACTED]');
      expect(storedRecords[0].outputs!.name).toBe('alice');
    });

    it('should redact nested fields', async () => {
      const tool = makeTool('tool', async () => 'ok');
      const audited = withAudit(tool, {
        store,
        redactInputFields: ['secret'],
      });

      await audited.execute(
        { config: { secret: 'hidden', public: 'visible' } },
        ctx
      );
      const inputs = storedRecords[0].inputs as Record<string, unknown>;
      const config = inputs.config as Record<string, unknown>;
      expect(config.secret).toBe('[REDACTED]');
      expect(config.public).toBe('visible');
    });

    it('should not redact when redactInputFields is empty', async () => {
      const tool = makeTool('tool', async () => 'ok');
      const audited = withAudit(tool, { store });

      await audited.execute({ password: 'secret' }, ctx);
      expect(storedRecords[0].inputs.password).toBe('secret');
    });
  });
});

describe('createAuditedToolRegistry', () => {
  it('should wrap all tools with audit middleware', async () => {
    const storedRecords: AuditRecord[] = [];
    const store: AuditStore = {
      store: vi.fn(async (record: AuditRecord) => {
        storedRecords.push(record);
      }),
      get: vi.fn(),
      query: vi.fn(),
    };
    const ctx = makeContext();

    const tool1 = makeTool('tool1', async () => 'result1');
    const tool2 = makeTool('tool2', async () => 'result2');

    const auditedTools = createAuditedToolRegistry([tool1, tool2], { store });
    expect(auditedTools.length).toBe(2);

    const result1 = await auditedTools[0].execute({}, ctx);
    expect(result1).toBe('result1');

    const result2 = await auditedTools[1].execute({}, ctx);
    expect(result2).toBe('result2');

    expect(storedRecords.length).toBe(2);
    expect(storedRecords[0].toolName).toBe('tool1');
    expect(storedRecords[1].toolName).toBe('tool2');
  });
});