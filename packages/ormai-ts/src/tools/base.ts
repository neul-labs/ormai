/**
 * Base tool class and result types.
 */

import type { ZodType, ZodTypeDef } from 'zod';
import { zodToJsonSchema } from 'zod-to-json-schema';
import type { RunContext } from '../core/context.js';
import { isOrmAIError } from '../core/errors.js';

/**
 * Result of a tool execution.
 */
export interface ToolResult<T> {
  success: boolean;
  data: T | null;
  error: Record<string, unknown> | null;
}

/**
 * Create a successful result.
 */
export function ok<T>(data: T): ToolResult<T> {
  return { success: true, data, error: null };
}

/**
 * Create a failed result.
 */
export function fail<T>(error: Record<string, unknown>): ToolResult<T> {
  return { success: false, data: null, error };
}

/**
 * Abstract interface for OrmAI tools.
 *
 * Tools are the primary interface for agents to interact with the database.
 * Each tool:
 * - Has a name and description for LLM consumption
 * - Defines a Zod input schema
 * - Executes within a RunContext with policy enforcement
 * - Returns a typed result
 */
export interface Tool<Input, Output> {
  /** Tool name (e.g., "db.query") */
  readonly name: string;

  /** Tool description for LLM */
  readonly description: string;

  /** Zod schema for input validation */
  readonly inputSchema: ZodType<Input, ZodTypeDef, unknown>;

  /**
   * Execute the tool with the given input and context.
   *
   * Implementations should:
   * 1. Validate input against policies
   * 2. Execute the operation
   * 3. Apply any post-processing (redaction, etc.)
   * 4. Return the result
   *
   * Throws OrmAIError subclasses for policy violations.
   */
  execute(input: Input, ctx: RunContext): Promise<Output>;
}

/**
 * Base class for implementing tools.
 */
export abstract class BaseTool<Input, Output> implements Tool<Input, Output> {
  abstract readonly name: string;
  abstract readonly description: string;
  abstract readonly inputSchema: ZodType<Input, ZodTypeDef, unknown>;

  abstract execute(input: Input, ctx: RunContext): Promise<Output>;

  /**
   * Run the tool with error handling.
   *
   * This is the main entry point for tool execution.
   * Returns a ToolResult wrapping the output or error.
   */
  async run(input: Input | Record<string, unknown>, ctx: RunContext): Promise<ToolResult<Output>> {
    try {
      // Validate input - always parse through schema for consistency
      const validatedInput = this.inputSchema.parse(input);

      const result = await this.execute(validatedInput, ctx);
      return ok(result);
    } catch (e) {
      if (isOrmAIError(e)) {
        return fail(e.toJSON());
      }
      return fail({
        code: 'INTERNAL_ERROR',
        message: e instanceof Error ? e.message : String(e),
      });
    }
  }

  /**
   * Get the JSON schema for this tool's input.
   *
   * Used for LLM tool descriptions and MCP exposure.
   */
  getJsonSchema(): Record<string, unknown> {
    return {
      name: this.name,
      description: this.description,
      parameters: zodToJsonSchema(this.inputSchema),
    };
  }
}

/**
 * Tool registry for managing multiple tools.
 */
export class ToolRegistry {
  private readonly tools: Map<string, Tool<unknown, unknown>> = new Map();

  /**
   * Register a tool.
   */
  register<I, O>(tool: Tool<I, O>): this {
    this.tools.set(tool.name, tool as Tool<unknown, unknown>);
    return this;
  }

  /**
   * Get a tool by name.
   */
  get<I, O>(name: string): Tool<I, O> | undefined {
    return this.tools.get(name) as Tool<I, O> | undefined;
  }

  /**
   * List all registered tools.
   */
  list(): Tool<unknown, unknown>[] {
    return Array.from(this.tools.values());
  }

  /**
   * Get all tool names.
   */
  names(): string[] {
    return Array.from(this.tools.keys());
  }

  /**
   * Get all tools as [name, tool] entries.
   */
  entries(): [string, Tool<unknown, unknown>][] {
    return Array.from(this.tools.entries());
  }

  /**
   * Get JSON schemas for all tools.
   */
  getJsonSchemas(): Record<string, unknown>[] {
    return this.list().map((tool) => {
      if (tool instanceof BaseTool) {
        return tool.getJsonSchema();
      }
      return {
        name: tool.name,
        description: tool.description,
        parameters: zodToJsonSchema(tool.inputSchema),
      };
    });
  }
}

/**
 * Create a new tool registry.
 */
export function createToolRegistry(): ToolRegistry {
  return new ToolRegistry();
}
