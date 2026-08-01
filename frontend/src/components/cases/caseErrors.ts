// src/components/cases/caseErrors.ts
// Maps workbench case API errors to actionable UI kinds.

export type CaseErrorKind =
  | 'conflict'
  | 'forbidden'
  | 'not_found'
  | 'validation'
  | 'service_unavailable'
  | 'approval_required'
  | 'unknown';

export interface CaseError {
  kind: CaseErrorKind;
  message: string;
}

interface ErrShape {
  response?: { status?: number; data?: { error?: string; message?: string; detail?: unknown } };
  message?: string;
}

export function parseCaseError(err: unknown): CaseError {
  const e = err as ErrShape;
  const status = e?.response?.status;
  const data = e?.response?.data;
  const code = data?.error;

  if (status === 428 || code === 'APPROVAL_REQUIRED') {
    return { kind: 'approval_required', message: data?.message ?? 'Approval not yet granted — waiting for compliance approval.' };
  }
  if (status === 409 || code === 'VERSION_CONFLICT' || code === 'INVALID_TRANSITION'
      || code === 'IDEMPOTENCY_MISMATCH' || code === 'APPROVAL_EXECUTED') {
    return { kind: 'conflict', message: data?.message ?? 'Case was updated — refresh and try again.' };
  }
  if (status === 403 || code === 'FORBIDDEN') {
    return { kind: 'forbidden', message: data?.message ?? 'You do not have permission to perform this action.' };
  }
  if (status === 404 || code === 'NOT_FOUND') {
    return { kind: 'not_found', message: data?.message ?? 'Case not found.' };
  }
  if (status === 422) {
    return { kind: 'validation', message: data?.message ?? 'Please correct the form and try again.' };
  }
  if (status === 503 || code === 'DB_UNAVAILABLE') {
    return { kind: 'service_unavailable', message: data?.message ?? 'Service temporarily unavailable. Please try again later.' };
  }
  return { kind: 'unknown', message: e?.message ?? 'Something went wrong. Please try again.' };
}
