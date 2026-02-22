/**
 * Proxies POST /api/analyze to the Python serverless function at /api/run-analyze.
 * This ensures the analyze endpoint works when both Next.js and Python run on Vercel.
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const PYTHON_ANALYZE_URL =
  process.env.VERCEL_URL
    ? `https://${process.env.VERCEL_URL}/api/run-analyze`
    : "http://127.0.0.1:8000/api/analyze";

export async function POST(request: Request) {
  try {
    const contentType = request.headers.get("content-type") || "";
    const body = await request.arrayBuffer();
    const headers: HeadersInit = {
      "content-type": contentType,
    };

    const res = await fetch(PYTHON_ANALYZE_URL, {
      method: "POST",
      body,
      headers,
    });

    const text = await res.text();
    if (!res.ok) {
      return new Response(text, {
        status: res.status,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(text, {
      status: res.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Backend request failed";
    return new Response(
      JSON.stringify({
        detail:
          message.includes("fetch") || message.includes("ECONNREFUSED")
            ? "Analysis service unavailable. If running locally, start the backend: python app.py (from project root)."
            : message,
      }),
      {
        status: 503,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
}
