import { defineConfig } from 'vitest/config';
import { resolve } from 'path';

export default defineConfig({
  resolve: {
    alias: {
      '@ormai/core': resolve(__dirname, 'packages/core/src/index.ts'),
      '@ormai/prisma': resolve(__dirname, 'packages/prisma/src/index.ts'),
      '@ormai/drizzle': resolve(__dirname, 'packages/drizzle/src/index.ts'),
      '@ormai/typeorm': resolve(__dirname, 'packages/typeorm/src/index.ts'),
      '@ormai/tools': resolve(__dirname, 'packages/tools/src/index.ts'),
      '@ormai/store': resolve(__dirname, 'packages/store/src/index.ts'),
      '@ormai/mcp': resolve(__dirname, 'packages/mcp/src/index.ts'),
      '@ormai/integrations': resolve(__dirname, 'packages/integrations/src/index.ts'),
      '@ormai/utils': resolve(__dirname, 'packages/utils/src/index.ts'),
    },
  },
  test: {
    globals: true,
    environment: 'node',
    include: [
      'packages/*/tests/**/*.test.ts',
      'tests/**/*.test.ts',
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['packages/*/src/**/*.ts'],
      exclude: ['packages/*/src/**/index.ts'],
    },
  },
});