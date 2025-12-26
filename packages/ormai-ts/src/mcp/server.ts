/**
 * MCP (Model Context Protocol) server for OrmAI.
 */

import type { RunContext } from '../core/context.js';
import type { Tool } from '../tools/base.js';
import type { ToolRegistry } from '../tools/base.js';
import type { AuditStore } from '../store/base.js';
import type { AuthMiddleware, AuthResult } from './auth.js';
import { zodToJsonSchema } from 'zod-to-json-schema';

/**
 * MCP tool definition (JSON Schema format).
 */
export interface McpToolDefinition {
  name: string;
  description: string;
  inputSchema: {
    type: 'object';
    properties: Record<string, unknown>;
    required?: string[];
    additionalProperties?: boolean;
  };
}

/**
 * MCP tool call request.
 */
export interface McpToolCallRequest {
  name: string;
  arguments: Record<string, unknown>;
}

/**
 * MCP tool call result.
 */
export interface McpToolCallResult {
  content: Array<{
    type: 'text';
    text: string;
  }>;
  isError?: boolean;
}

/**
 * MCP server configuration.
 */
export interface McpServerConfig<DB> {
  /** Name of the MCP server */
  name: string;

  /** Version of the MCP server */
  version: string;

  /** Tool registry */
  registry: ToolRegistry;

  /** Context factory */
  createContext: (authResult: AuthResult, requestId?: string) => RunContext<DB>;

  /** Optional auth middleware */
  authMiddleware?: AuthMiddleware;

  /** Optional audit store */
  auditStore?: AuditStore;

  /** Optional tool name prefix */
  toolPrefix?: string;
}

/**
 * MCP server for exposing OrmAI tools via the Model Context Protocol.
 */
export class McpServer<DB> {
  private readonly config: McpServerConfig<DB>;
  private readonly tools: Map<string, Tool<unknown, unknown>>;
  private readonly toolDefinitions: McpToolDefinition[];

  constructor(config: McpServerConfig<DB>) {
    this.config = config;
    this.tools = new Map();
    this.toolDefinitions = [];

    // Register all tools from registry
    for (const tool of config.registry.list()) {
      const name = config.toolPrefix ? `${config.toolPrefix}_${tool.name}` : tool.name;
      this.tools.set(name, tool);

      // Convert Zod schema to JSON Schema
      const jsonSchema = zodToJsonSchema(tool.inputSchema, { target: 'openApi3' });
      const schema = (typeof jsonSchema === 'object' && jsonSchema !== null)
        ? jsonSchema
        : { type: 'object', properties: {} };

      this.toolDefinitions.push({
        name,
        description: tool.description,
        inputSchema: {
          type: 'object',
          properties: (schema as Record<string, unknown>).properties as Record<string, unknown> ?? {},
          required: (schema as Record<string, unknown>).required as string[] | undefined,
          additionalProperties: false,
        },
      });
    }
  }

  /**
   * Get server info.
   */
  getServerInfo(): { name: string; version: string } {
    return {
      name: this.config.name,
      version: this.config.version,
    };
  }

  /**
   * List available tools.
   */
  listTools(): McpToolDefinition[] {
    return this.toolDefinitions;
  }

  /**
   * Call a tool.
   */
  async callTool(
    request: McpToolCallRequest,
    headers?: Record<string, string | undefined>
  ): Promise<McpToolCallResult> {
    const requestId = crypto.randomUUID();

    // Authenticate if middleware is configured
    let authResult: AuthResult = { authenticated: true };
    if (this.config.authMiddleware && headers) {
      authResult = await this.config.authMiddleware(headers);
      if (!authResult.authenticated) {
        return {
          content: [{ type: 'text', text: `Authentication failed: ${authResult.error}` }],
          isError: true,
        };
      }
    }

    // Get the tool
    const tool = this.tools.get(request.name);
    if (!tool) {
      return {
        content: [{ type: 'text', text: `Unknown tool: ${request.name}` }],
        isError: true,
      };
    }

    // Create context
    const ctx = this.config.createContext(authResult, requestId);

    // Execute the tool
    const startTime = Date.now();
    try {
      const result = await tool.execute(request.arguments, ctx);
      const durationMs = Date.now() - startTime;

      // Audit if store is configured
      if (this.config.auditStore) {
        await this.config.auditStore.store({
          id: requestId,
          toolName: request.name,
          principalId: ctx.principal.userId,
          tenantId: ctx.principal.tenantId,
          requestId,
          timestamp: ctx.now,
          durationMs,
          inputs: request.arguments,
          outputs: result as Record<string, unknown>,
          policyDecisions: [],
        });
      }

      return {
        content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
      };
    } catch (error) {
      const durationMs = Date.now() - startTime;

      // Audit error if store is configured
      if (this.config.auditStore) {
        await this.config.auditStore.store({
          id: requestId,
          toolName: request.name,
          principalId: ctx.principal.userId,
          tenantId: ctx.principal.tenantId,
          requestId,
          timestamp: ctx.now,
          durationMs,
          inputs: request.arguments,
          policyDecisions: [],
          error: {
            type: 'ExecutionError',
            code: (error as { code?: string }).code ?? 'UNKNOWN_ERROR',
            message: (error as Error).message,
            details: {},
          },
        });
      }

      return {
        content: [{ type: 'text', text: (error as Error).message }],
        isError: true,
      };
    }
  }

  /**
   * Handle an MCP JSON-RPC request.
   */
  async handleRequest(
    request: {
      jsonrpc: '2.0';
      id: string | number;
      method: string;
      params?: unknown;
    },
    headers?: Record<string, string | undefined>
  ): Promise<{
    jsonrpc: '2.0';
    id: string | number;
    result?: unknown;
    error?: { code: number; message: string };
  }> {
    try {
      switch (request.method) {
        case 'initialize':
          return {
            jsonrpc: '2.0',
            id: request.id,
            result: {
              protocolVersion: '2024-11-05',
              capabilities: {
                tools: {},
              },
              serverInfo: this.getServerInfo(),
            },
          };

        case 'tools/list':
          return {
            jsonrpc: '2.0',
            id: request.id,
            result: {
              tools: this.listTools(),
            },
          };

        case 'tools/call': {
          const params = request.params as { name: string; arguments?: Record<string, unknown> };
          const result = await this.callTool(
            { name: params.name, arguments: params.arguments ?? {} },
            headers
          );
          return {
            jsonrpc: '2.0',
            id: request.id,
            result,
          };
        }

        default:
          return {
            jsonrpc: '2.0',
            id: request.id,
            error: { code: -32601, message: `Method not found: ${request.method}` },
          };
      }
    } catch (error) {
      return {
        jsonrpc: '2.0',
        id: request.id,
        error: { code: -32603, message: (error as Error).message },
      };
    }
  }

  /**
   * Create a stdio transport handler for the MCP server.
   * Returns functions for handling stdin/stdout communication.
   */
  createStdioTransport(): {
    handleLine: (line: string) => Promise<string | undefined>;
  } {
    return {
      handleLine: async (line: string) => {
        try {
          const request = JSON.parse(line);
          if (request.method === 'notifications/initialized') {
            // Ignore notification
            return undefined;
          }
          const response = await this.handleRequest(request);
          return JSON.stringify(response);
        } catch (error) {
          return JSON.stringify({
            jsonrpc: '2.0',
            id: null,
            error: { code: -32700, message: `Parse error: ${(error as Error).message}` },
          });
        }
      },
    };
  }

  /**
   * Start the MCP server with stdio transport.
   */
  async runStdio(): Promise<void> {
    const transport = this.createStdioTransport();
    const readline = await import('readline');

    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
      terminal: false,
    });

    rl.on('line', async (line) => {
      const response = await transport.handleLine(line);
      if (response) {
        console.log(response);
      }
    });

    rl.on('close', () => {
      process.exit(0);
    });
  }
}

/**
 * Create an MCP server.
 */
export function createMcpServer<DB>(config: McpServerConfig<DB>): McpServer<DB> {
  return new McpServer(config);
}

/**
 * Create a simplified MCP server for quick setup.
 */
export function createSimpleMcpServer<DB>(options: {
  name?: string;
  version?: string;
  registry: ToolRegistry;
  db: DB;
  defaultTenantId?: string;
  defaultUserId?: string;
  authMiddleware?: AuthMiddleware;
  auditStore?: AuditStore;
}): McpServer<DB> {
  const {
    name = 'ormai-mcp',
    version = '1.0.0',
    registry,
    db,
    defaultTenantId = 'default',
    defaultUserId = 'anonymous',
    authMiddleware,
    auditStore,
  } = options;

  return createMcpServer({
    name,
    version,
    registry,
    createContext: (authResult, requestId) => {
      const principal = authResult.principal ?? {
        tenantId: defaultTenantId,
        userId: defaultUserId,
        roles: [],
      };

      return {
        principal,
        db,
        requestId: requestId ?? crypto.randomUUID(),
        now: new Date(),
      };
    },
    authMiddleware,
    auditStore,
  });
}
