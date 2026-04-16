import { defineConfig } from 'tsup';

export default defineConfig({
  entry: ['src/index.ts'],
  format: ['esm', 'cjs'],
  dts: true,
  sourcemap: true,
  clean: true,
  splitting: false,
  treeshake: true,
  external: ['@ormai/core', 'zod-to-json-schema', '@langchain/core', 'ai', 'openai', '@anthropic-ai/sdk', 'llamaindex', '@mastra/core'],
});