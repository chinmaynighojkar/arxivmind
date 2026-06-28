import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api-client";

export async function GET() {
  try {
    const data = await apiGet("/papers");
    return NextResponse.json(data);
  } catch (err: unknown) {
    const e = err as { status?: number; detail?: string };
    return NextResponse.json({ detail: e.detail ?? "Internal error" }, { status: e.status ?? 500 });
  }
}
