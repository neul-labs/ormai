# @ormai/integrations

Agent framework integrations for Vercel AI SDK, LangChain.js, OpenAI, Anthropic, LlamaIndex, and Mastra.

[![npm version](https://img.shields.io/npm/v/@ormai/integrations)](https://www.npmjs.com/package/@ormai/integrations) [![license](https://img.shields.io/npm/l/@ormai/integrations)](https://github.com/neul-labs/ormai/blob/main/ormai-ts/packages/integrations/LICENSE) [![CI](https://img.shields.io/github/actions/workflow/status/neul-labs/ormai/test.yml)](https://github.com/neul-labs/ormai/actions)

`@ormai/integrations` converts OrmAI tools into the native tool formats expected by popular agent frameworks. All peer dependencies are optional -- install only the framework packages you need.

| Framework | Function | Returns |
|-----------|----------|---------|
| Vercel AI SDK | `toVercelAITools()` | Tools for `generateText`/`streamText` |
| LangChain.js | `toLangChainTools()` | `DynamicStructuredTool[]` |
| OpenAI SDK | `toOpenAITools()` | OpenAI function definitions |
| Anthropic SDK | `toAnthropicTools()` | Claude tool definitions |
| LlamaIndex.ts | `toLlamaIndexTools()` | `FunctionTool[]` |
| Mastra | `toMastraTools()` | Mastra-compatible tools |
| Generic | `toJsonSchemas()` | JSON Schema definitions |

## Installation

```bash
npm install @ormai/core @ormai/integrations
# Plus the agent framework you want to use, e.g.:
npm install ai @ai-sdk/openai
```

## Quick Start

### Vercel AI SDK

```typescript
import { toVercelAITools } from '@ormai/integrations';
import { generateText } from 'ai';
import { openai } from '@ai-sdk/openai';

const tools = await toVercelAITools(registry.list(), ctx);

const result = await generateText({
  model: openai('gpt-4o'),
  tools,
  prompt: 'Find all pending orders for the current tenant',
});
```

### LangChain.js

```typescript
import { toLangChainTools } from '@ormai/integrations';
import { ChatOpenAI } from '@langchain/openai';
import { AgentExecutor, createToolCallingAgent } from 'langchain/agents';

const tools = await toLangChainTools(registry.list(), ctx);

const agent = createToolCallingAgent({
  llm: new ChatOpenAI({ model: 'gpt-4o' }),
  tools,
  prompt: hubPrompt,
});
```

### OpenAI / Anthropic

```typescript
import { toOpenAITools, executeOpenAIFunctionCall } from '@ormai/integrations';
import { toAnthropicTools, executeAnthropicToolCall } from '@ormai/integrations';
```

## API Reference

- `toVercelAITools(tools, ctx)` / `createVercelAITools(registry, ctx)`
- `toLangChainTools(tools, ctx)` / `toLangChainToolDefinitions(tools)` / `createLangChainTools(registry, ctx)`
- `toOpenAITools(tools)` / `toOpenAIFunctions(tools)` / `executeOpenAIFunctionCall(call, tools, ctx)` / `createOpenAIToolHandler(tools, ctx)`
- `toAnthropicTools(tools)` / `executeAnthropicToolCall(call, tools, ctx)` / `createAnthropicToolHandler(tools, ctx)` / `formatAnthropicToolResult(result)`
- `toLlamaIndexTools(tools, ctx)` / `createLlamaIndexTools(registry, ctx)`
- `toMastraTools(tools, ctx)` / `createMastraTools(registry, ctx)`
- `toJsonSchemas(tools)` / `toJsonSchema(tool)` / `exportToolSchemas(registry)` / `toolSchemasToMap(registry)`

## Related Packages

- [@ormai/core](../core/) -- Core types and tool registry
- [@ormai/tools](../tools/) -- Generic database tools
- [@ormai/mcp](../mcp/) -- MCP server

## License

MIT