/**
 * Agent framework integrations for OrmAI.
 */

// Vercel AI SDK
export {
  type VercelAITool,
  toVercelAITools,
  createVercelAITools,
} from './vercel-ai.js';

// LangChain.js
export {
  type LangChainToolDefinition,
  toLangChainTools,
  toLangChainToolDefinitions,
  createLangChainTools,
} from './langchain.js';

// OpenAI SDK
export {
  type OpenAIFunction,
  type OpenAIToolDefinition,
  toOpenAIFunctions,
  toOpenAITools,
  executeOpenAIFunctionCall,
  createOpenAIToolHandler,
} from './openai.js';

// Anthropic SDK
export {
  type AnthropicTool,
  toAnthropicTools,
  executeAnthropicToolCall,
  createAnthropicToolHandler,
  formatAnthropicToolResult,
} from './anthropic.js';

// LlamaIndex.ts
export {
  type LlamaIndexToolDefinition,
  toLlamaIndexTools,
  createLlamaIndexTools,
} from './llamaindex.js';

// Mastra
export {
  type MastraToolDefinition,
  toMastraTools,
  createMastraTools,
} from './mastra.js';

// JSON Schema (universal)
export {
  type JsonSchemaTool,
  toJsonSchema,
  toJsonSchemas,
  exportToolSchemas,
  toolSchemasToMap,
} from './json-schema.js';
