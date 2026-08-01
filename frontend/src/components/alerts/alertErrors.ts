// src/components/alerts/alertErrors.ts
// Maps workbench API errors to actionable UI kinds.

export type AlertErrorKind =
  | 'conflict'
  | 'approval_required'
  | 'forbidden'
  | 'not_found'
  | 'validation'
  | 'unknown';

interface AlertError {
  kind: AlertErrorKind;
  message: string;
}

interface ErrShape {
  response?: { status?: number; data?: { error?: string; message?: string; detail?: unknown } };
  message?: string;
}

export function parseAlertError(err: unknown): AlertError {
  const e = err as ErrShape;
  const status = e?.response?.status;
  const data = e?.response?.data;
  const code = data?.error;

  if (status === 409 || code === 'VERSION_CONFLICT' || code === 'INVALID_TRANSITION'
      || code === 'APPROVAL_EXECUTED' || code === 'IDEMPOTENCY_MISMATCH') {
    return { kind: 'conflict', message: data?.message ?? 'Alert was updated — refresh and try again.' };
  }
  if (status === 428 || code === 'APPROVAL_REQUIRED') {
    return { kind: 'approval_required', message: data?.message ?? 'Approval not yet granted — waiting for compliance officer.' };
  }
  if (status === 403) {
    return { kind: 'forbidden', message: data?.message ?? 'You do not have permission to perform this action.' };
  }
  if (status === 404) {
    return { kind: 'not_found', message: data?.message ?? 'Alert not found.' };
  }
  if (status === 422) {
    return { kind: 'validation', message: data?.message ?? 'Please correct the form and try again.' };
  }
  return { kind: 'unknown', message: e?.message ?? 'Something went wrong. Please try again.' };
}
