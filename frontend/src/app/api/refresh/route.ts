import { NextResponse } from "next/server";
import { apiPost } from "@/lib/api-client";

export async function POST() {
  try {
    const data = await apiPost("/refresh", {});
    return NextResponse.json(data);
  } catch (err: unknown) {
    const e = err as { status?: number; detail?: string };
    return NextResponse.json({ detail: e.detail ?? "Internal error" }, { status: e.status ?? 500 });
  }
}
