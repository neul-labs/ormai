/**
 * Anthropic SDK integration.
 *
 * Converts OrmAI tools to Anthropic tool_use format.
 */

import { zodToJsonSchema } from 'zod-to-json-schema';
import type { RunContext } from '../core/context.js';
import type { Tool } from '../tools/base.js';

/**
 * Anthropic tool definition.
 */
export interface AnthropicTool {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
}

/**
 * Convert OrmAI tools to Anthropic tool definitions.
 *
 * @param tools - OrmAI tools to convert
 * @returns Array of Anthropic tool definitions
 */
export function toAnthropicTools<T extends Tool<unknown, unknown>[]>(
  tools: T
): AnthropicTool[] {
  return tools.map((tool) => ({
    name: tool.name,
    description: tool.description,
    input_schema: zodToJsonSchema(tool.inputSchema),
  }));
}

/**
 * Execute a tool call from Anthropic's response.
 *
 * @param tools - Available OrmAI tools
 * @param toolName - Name of the tool to call
 * @param toolInput - Input from Anthropic (as object)
 * @param ctx - Run context
 * @returns Tool execution result
 */
export async function executeAnthropicToolCall<T extends Tool<unknown, unknown>[]>(
  tools: T,
  toolName: string,
  toolInput: Record<string, unknown>,
  ctx: RunContext
): Promise<unknown> {
  const tool = tools.find((t) => t.name === toolName);
  if (!tool) {
    throw new Error(`Unknown tool: ${toolName}`);
  }

  return tool.execute(toolInput, ctx);
}

/**
 * Create a function to handle Anthropic tool calls.
 *
 * Usage with Anthropic SDK:
 * ```ts
 * import Anthropic from '@anthropic-ai/sdk';
 *
 * const client = new Anthropic();
 * const tools = toAnthropicTools(registry.list());
 * const handleToolCall = createAnthropicToolHandler(registry.list(), ctx);
 *
 * const response = await client.messages.create({
 *   model: 'claude-3-opus-20240229',
 *   max_tokens: 4096,
 *   tools,
 *   messages: [...],
 * });
 *
 * for (const block of response.content) {
 *   if (block.type === 'tool_use') {
 *     const result = await handleToolCall(block.name, block.input);
 *     // Add tool result to messages...
 *   }
 * }
 * ```
 */
export function createAnthropicToolHandler<T extends Tool<unknown, unknown>[]>(
  tools: T,
  ctx: RunContext
): (toolName: string, toolInput: Record<string, unknown>) => Promise<unknown> {
  return (toolName, toolInput) => executeAnthropicToolCall(tools, toolName, toolInput, ctx);
}

/**
 * Format a tool result for Anthropic's messages format.
 */
export function formatAnthropicToolResult(
  toolUseId: string,
  result: unknown,
  isError = false
): {
  type: 'tool_result';
  tool_use_id: string;
  content: string;
  is_error?: boolean;
} {
  return {
    type: 'tool_result',
    tool_use_id: toolUseId,
    content: typeof result === 'string' ? result : JSON.stringify(result),
    ...(isError ? { is_error: true } : {}),
  };
}
