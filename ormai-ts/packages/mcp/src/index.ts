/**
 * MCP (Model Context Protocol) module for OrmAI.
 */

// Auth
export {
  type AuthResult,
  type AuthMiddleware,
  createApiKeyAuth,
  createJwtAuth,
  createContextFactory,
  extractTenantFromHeaders,
  principalFromHeaders,
  combineAuthMiddlewares,
  createDevAuth,
} from './auth.js';

// Server
export {
  type McpToolDefinition,
  type McpToolCallRequest,
  type McpToolCallResult,
  type McpServerConfig,
  McpServer,
  createMcpServer,
  createSimpleMcpServer,
} from './server.js';
