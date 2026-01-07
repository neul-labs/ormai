/**
 * Tests for tools/base.ts
 */

import { describe, it, expect, vi } from 'vitest';
import { z } from 'zod';
import {
  ok,
  fail,
  BaseTool,
  ToolRegistry,
  createToolRegistry,
  type ToolResult,
} from '../../src/tools/base.js';
import { createContext, type RunContext } from '../../src/core/context.js';
import { OrmAIError, ErrorCodes } from '../../src/core/errors.js';

function createTestContext(): RunContext {
  return createContext({
    tenantId: 'tenant-123',
    userId: 'user-456',
    db: {},
  });
}

describe('ok', () => {
  it('should create successful result', () => {
    const result = ok({ id: '123', name: 'Test' });

    expect(result.success).toBe(true);
    expect(result.data).toEqual({ id: '123', name: 'Test' });
    expect(result.error).toBeNull();
  });

  it('should work with any data type', () => {
    expect(ok(42).data).toBe(42);
    expect(ok('string').data).toBe('string');
    expect(ok(['a', 'b']).data).toEqual(['a', 'b']);
    expect(ok(null).data).toBeNull();
  });
});

describe('fail', () => {
  it('should create failed result', () => {
    const result = fail({ code: 'ERROR', message: 'Something went wrong' });

    expect(result.success).toBe(false);
    expect(result.data).toBeNull();
    expect(result.error).toEqual({ code: 'ERROR', message: 'Something went wrong' });
  });
});

// Test implementation of BaseTool
class TestTool extends BaseTool<{ name: string }, { greeting: string }> {
  readonly name = 'test.greet';
  readonly description = 'A test greeting tool';
  readonly inputSchema = z.object({
    name: z.string().min(1),
  });

  async execute(input: { name: string }, _ctx: RunContext): Promise<{ greeting: string }> {
    return { greeting: `Hello, ${input.name}!` };
  }
}

class ErrorTool extends BaseTool<{ shouldFail: boolean }, string> {
  readonly name = 'test.error';
  readonly description = 'A tool that can fail';
  readonly inputSchema = z.object({
    shouldFail: z.boolean(),
  });

  async execute(input: { shouldFail: boolean }, _ctx: RunContext): Promise<string> {
    if (input.shouldFail) {
      throw new OrmAIError(ErrorCodes.INTERNAL_ERROR, 'Intentional error');
    }
    return 'success';
  }
}

describe('BaseTool', () => {
  describe('execute', () => {
    it('should execute and return result', async () => {
      const tool = new TestTool();
      const ctx = createTestContext();

      const result = await tool.execute({ name: 'World' }, ctx);

      expect(result.greeting).toBe('Hello, World!');
    });
  });

  describe('run', () => {
    it('should run and return successful result', async () => {
      const tool = new TestTool();
      const ctx = createTestContext();

      const result = await tool.run({ name: 'World' }, ctx);

      expect(result.success).toBe(true);
      expect(result.data).toEqual({ greeting: 'Hello, World!' });
    });

    it('should validate input and reject invalid data', async () => {
      const tool = new TestTool();
      const ctx = createTestContext();

      const result = await tool.run({ name: '' }, ctx);

      expect(result.success).toBe(false);
      expect(result.error?.code).toBe('INTERNAL_ERROR');
    });

    it('should handle OrmAIError', async () => {
      const tool = new ErrorTool();
      const ctx = createTestContext();

      const result = await tool.run({ shouldFail: true }, ctx);

      expect(result.success).toBe(false);
      // toJSON returns the error in a structured format
      expect(result.error?.code).toBeDefined();
      expect(result.error?.message).toBe('Intentional error');
    });

    it('should handle regular errors', async () => {
      class BrokenTool extends BaseTool<object, string> {
        readonly name = 'test.broken';
        readonly description = 'A broken tool';
        readonly inputSchema = z.object({});

        async execute(): Promise<string> {
          throw new Error('Unexpected error');
        }
      }

      const tool = new BrokenTool();
      const ctx = createTestContext();

      const result = await tool.run({}, ctx);

      expect(result.success).toBe(false);
      expect(result.error?.code).toBe('INTERNAL_ERROR');
      expect(result.error?.message).toBe('Unexpected error');
    });
  });

  describe('getJsonSchema', () => {
    it('should return JSON schema for tool', () => {
      const tool = new TestTool();

      const schema = tool.getJsonSchema();

      expect(schema.name).toBe('test.greet');
      expect(schema.description).toBe('A test greeting tool');
      expect(schema.parameters).toBeDefined();
    });
  });
});

describe('ToolRegistry', () => {
  describe('register', () => {
    it('should register a tool', () => {
      const registry = new ToolRegistry();
      const tool = new TestTool();

      registry.register(tool);

      expect(registry.get('test.greet')).toBe(tool);
    });

    it('should support chaining', () => {
      const registry = new ToolRegistry();
      const tool1 = new TestTool();
      const tool2 = new ErrorTool();

      registry.register(tool1).register(tool2);

      expect(registry.names()).toContain('test.greet');
      expect(registry.names()).toContain('test.error');
    });
  });

  describe('get', () => {
    it('should return registered tool', () => {
      const registry = new ToolRegistry();
      const tool = new TestTool();
      registry.register(tool);

      const retrieved = registry.get<{ name: string }, { greeting: string }>('test.greet');

      expect(retrieved).toBe(tool);
    });

    it('should return undefined for unregistered tool', () => {
      const registry = new ToolRegistry();

      expect(registry.get('nonexistent')).toBeUndefined();
    });
  });

  describe('list', () => {
    it('should return all registered tools', () => {
      const registry = new ToolRegistry();
      const tool1 = new TestTool();
      const tool2 = new ErrorTool();

      registry.register(tool1).register(tool2);

      const tools = registry.list();

      expect(tools).toHaveLength(2);
      expect(tools).toContain(tool1);
      expect(tools).toContain(tool2);
    });

    it('should return empty array for empty registry', () => {
      const registry = new ToolRegistry();

      expect(registry.list()).toEqual([]);
    });
  });

  describe('names', () => {
    it('should return all tool names', () => {
      const registry = new ToolRegistry();
      registry.register(new TestTool());
      registry.register(new ErrorTool());

      const names = registry.names();

      expect(names).toContain('test.greet');
      expect(names).toContain('test.error');
    });
  });

  describe('entries', () => {
    it('should return all tool entries', () => {
      const registry = new ToolRegistry();
      const tool = new TestTool();
      registry.register(tool);

      const entries = registry.entries();

      expect(entries).toHaveLength(1);
      expect(entries[0][0]).toBe('test.greet');
      expect(entries[0][1]).toBe(tool);
    });
  });

  describe('getJsonSchemas', () => {
    it('should return JSON schemas for all tools', () => {
      const registry = new ToolRegistry();
      registry.register(new TestTool());
      registry.register(new ErrorTool());

      const schemas = registry.getJsonSchemas();

      expect(schemas).toHaveLength(2);
      expect(schemas.some(s => s.name === 'test.greet')).toBe(true);
      expect(schemas.some(s => s.name === 'test.error')).toBe(true);
    });
  });
});

describe('createToolRegistry', () => {
  it('should create a new registry', () => {
    const registry = createToolRegistry();

    expect(registry).toBeInstanceOf(ToolRegistry);
    expect(registry.list()).toEqual([]);
  });
});
