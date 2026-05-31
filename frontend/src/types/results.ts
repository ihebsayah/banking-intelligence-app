// src/types/results.ts

export interface TableColumn {
  key: string;
  label: string;
  type: 'string' | 'number' | 'boolean' | 'date' | 'unknown';
  sortable: boolean;
}

export interface TableData {
  columns: TableColumn[];
  rows: Record<string, unknown>[];
  totalRows: number;
}

export type SortDirection = 'asc' | 'desc';

export interface SortConfig {
  key: string;
  direction: SortDirection;
}

export interface FilterConfig {
  column: string;
  value: string;
}

export type TabId = 'json' | 'csv' | 'table' | 'metadata' | 'insights';

export interface SQLValidationResult {
  valid: boolean;
  safe: boolean;
  issues: string[];
  signature?: string;
  estimatedTimeMs?: number;
  estimatedRows?: number;
  rawInput?: string;
}

export interface RoleTestResult {
  role: string;
  status: 'success' | 'error';
  rowCount: number;
  maskedColumns: string[];
  filteredRows: number;
  executionTimeMs: number;
  sample?: unknown[];
  error?: string;
}

export interface PerformanceTestResult {
  concurrentQueries: number;
  totalTimeMs: number;
  avgResponseTimeMs: number;
  minResponseTimeMs: number;
  maxResponseTimeMs: number;
  p95ResponseTimeMs: number;
  successCount: number;
  errorCount: number;
  cacheHitRate: number;
  results: Array<{ queryIndex: number; durationMs: number; status: 'success' | 'error'; cached: boolean }>;
}
