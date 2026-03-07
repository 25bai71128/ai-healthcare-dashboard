import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";

const protectedPagePrefixes = ["/dashboard"];
const protectedApiPrefixes = [
  "/api/profile",
  "/api/appointments",
  "/api/medications",
  "/api/vitals",
  "/api/labs",
  "/api/alerts",
  "/api/timeline",
  "/api/assistant",
  "/api/analytics",
];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const needsPageAuth = protectedPagePrefixes.some((prefix) => pathname.startsWith(prefix));
  const needsApiAuth = protectedApiPrefixes.some((prefix) => pathname.startsWith(prefix));

  if (!needsPageAuth && !needsApiAuth) {
    return NextResponse.next();
  }

  const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET });

  if (token) {
    return NextResponse.next();
  }

  if (needsApiAuth) {
    return NextResponse.json(
      {
        ok: false,
        error: {
          code: "UNAUTHORIZED",
          message: "Authentication required",
        },
      },
      { status: 401 },
    );
  }

  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("redirect", pathname);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/dashboard/:path*", "/api/:path*"],
};
