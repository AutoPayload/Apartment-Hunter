import { NextResponse, type NextRequest } from "next/server";

import { AUTH_COOKIE, passwordToken } from "@/lib/auth";

export async function proxy(request: NextRequest) {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) return NextResponse.next(); // gate disabled (local dev)
  const token = request.cookies.get(AUTH_COOKIE)?.value;
  if (token === (await passwordToken(password))) return NextResponse.next();
  const url = new URL("/login", request.url);
  url.searchParams.set("next", request.nextUrl.pathname + request.nextUrl.search);
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!login|_next/static|_next/image|favicon.ico|icon.svg).*)"],
};
