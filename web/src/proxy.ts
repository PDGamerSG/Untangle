import { NextResponse, type NextRequest } from "next/server";

// An optimistic check only: the API validates every session and is the real access control. This sends visitors
// without a session cookie to sign-in before the workspace shell loads, instead of after its first request fails.
const SESSION_COOKIES = ["__Host-untangle_session", "untangle_session"];

export function proxy(request: NextRequest) {
  if (process.env.NEXT_PUBLIC_UNTANGLE_SAMPLE === "1") return NextResponse.next();
  if (SESSION_COOKIES.some((name) => request.cookies.has(name))) return NextResponse.next();
  const url = request.nextUrl.clone();
  const next = `${request.nextUrl.pathname}${request.nextUrl.search}`;
  url.pathname = "/login";
  url.search = `?next=${encodeURIComponent(next)}`;
  return NextResponse.redirect(url);
}

export const config = {
  matcher: [
    "/dashboard/:path*", "/ask/:path*", "/timeline/:path*", "/pulse/:path*", "/map/:path*", "/meetings/:path*",
    "/repositories/:path*", "/decisions/:path*", "/entities/:path*", "/explore/:path*", "/agents/:path*",
    "/preflight/:path*", "/briefing/:path*", "/benchmarks/:path*",
  ],
};
