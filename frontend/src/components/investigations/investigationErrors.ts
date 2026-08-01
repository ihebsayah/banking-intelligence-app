// src/components/investigations/investigationErrors.ts
// Maps workbench API errors to actionable UI kinds.

export type InvestigationErrorKind =
  | 'conflict'
  | 'forbidden'
  | 'not_found'
  | 'validation'
  | 'service_unavailable'
  | 'unknown';

export interface InvestigationError {
  kind: InvestigationErrorKind;
  message: string;
}

interface ErrShape {
  response?: { status?: number; data?: { error?: string; message?: string; detail?: unknown } };
  message?: string;
}

export function parseInvestigationError(err: unknown): InvestigationError {
  const e = err as ErrShape;
  const status = e?.response?.status;
  const data = e?.response?.data;
  const code = data?.error;

  if (status === 409 || code === 'VERSION_CONFLICT' || code === 'INVALID_TRANSITION'
      || code === 'IDEMPOTENCY_MISMATCH' || code === 'APPROVAL_EXECUTED') {
    return { kind: 'conflict', message: data?.message ?? 'Investigation was updated — refresh and try again.' };
  }
  if (status === 403 || code === 'FORBIDDEN') {
    return { kind: 'forbidden', message: data?.message ?? 'You do not have permission to perform this action.' };
  }
  if (status === 404 || code === 'NOT_FOUND') {
    return { kind: 'not_found', message: data?.message ?? 'Investigation not found.' };
  }
  if (status === 422) {
    return { kind: 'validation', message: data?.message ?? 'Please correct the form and try again.' };
  }
  if (status === 503 || code === 'DB_UNAVAILABLE') {
    return { kind: 'service_unavailable', message: data?.message ?? 'Service temporarily unavailable. Please try again later.' };
  }
  return { kind: 'unknown', message: e?.message ?? 'Something went wrong. Please try again.' };
}
