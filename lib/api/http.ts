import { NextResponse } from "next/server";

export class ApiError extends Error {
  status: number;
  code: string;
  details?: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function ok<T>(data: T, status = 200) {
  return NextResponse.json({ ok: true, data }, { status });
}

export function fail(status: number, code: string, message: string, details?: unknown) {
  return NextResponse.json(
    {
      ok: false,
      error: {
        code,
        message,
        details,
      },
    },
    { status },
  );
}

export function handleApiError(error: unknown) {
  if (error instanceof ApiError) {
    return fail(error.status, error.code, error.message, error.details);
  }

  if (error instanceof Error && error.message === "UNAUTHORIZED") {
    return fail(401, "UNAUTHORIZED", "Authentication is required.");
  }

  if (error instanceof Error) {
    return fail(500, "INTERNAL_ERROR", error.message);
  }

  return fail(500, "INTERNAL_ERROR", "Unknown server error.");
}
