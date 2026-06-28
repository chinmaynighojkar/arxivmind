import { NextRequest, NextResponse } from "next/server";
import { apiPost } from "@/lib/api-client";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const data = await apiPost("/query", body);
    return NextResponse.json(data);
  } catch (err: unknown) {
    const e = err as { status?: number; detail?: string };
    return NextResponse.json({ detail: e.detail ?? "Internal error" }, { status: e.status ?? 500 });
  }
}
