/**
 * Type declarations for optional peer dependencies.
 *
 * These declarations allow dynamic imports to work without compile-time errors.
 */

declare module '@langchain/core/tools' {
  export class DynamicStructuredTool {
    constructor(config: {
      name: string;
      description: string;
      schema: unknown;
      func: (input: unknown) => Promise<string>;
    });
  }
}

declare module 'llamaindex' {
  export class FunctionTool {
    static from(fn: (input: Record<string, unknown>) => Promise<string>, options: {
      name: string;
      description: string;
      parameters: unknown;
    }): FunctionTool;
  }
}

declare module '@mastra/core' {
  export function createTool(config: {
    id: string;
    description: string;
    inputSchema: unknown;
    execute: (options: { context: unknown }) => Promise<unknown>;
  }): unknown;
}
