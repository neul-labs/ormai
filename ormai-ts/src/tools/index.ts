/**
 * Tools module for OrmAI.
 *
 * Provides the tool interface and generic database tools.
 */

// Base
export {
  type ToolResult,
  type Tool,
  BaseTool,
  ToolRegistry,
  ok,
  fail,
  createToolRegistry,
} from './base.js';

// Generic tools
export {
  DescribeSchemaTool,
  QueryTool,
  GetTool,
  AggregateTool,
  CreateTool,
  UpdateTool,
  DeleteTool,
  BulkUpdateTool,
  createGenericTools,
  type GenericToolsOptions,
} from './generic.js';
