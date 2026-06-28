/**
 * Server-side FastAPI client with automatic token caching.
 * Credentials never leave the server — the browser only calls /api/* proxy routes.
 */

const API_URL = process.env.ARXIVMIND_API_URL ?? "http://localhost:8000";
const CLIENT_ID = process.env.ARXIVMIND_CLIENT_ID ?? "arxivmind-client";
const CLIENT_SECRET = process.env.ARXIVMIND_CLIENT_SECRET;
if (!CLIENT_SECRET) {
  throw new Error(
    "ARXIVMIND_CLIENT_SECRET is not set. Add it to frontend/.env.local before starting."
  );
}
const _clientSecret: string = CLIENT_SECRET;

let _token: string | null = null;
let _tokenExpiresAt = 0;

async function getToken(): Promise<string> {
  if (_token && Date.now() < _tokenExpiresAt) return _token;

  const form = new URLSearchParams();
  form.set("username", CLIENT_ID);
  form.set("password", _clientSecret);
  form.set("scope", "read:query write:ingest");

  const res = await fetch(`${API_URL}/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  });

  if (!res.ok) throw new Error(`Auth failed: ${res.status} ${res.statusText}`);

  const data = (await res.json()) as { access_token: string };
  _token = data.access_token;
  _tokenExpiresAt = Date.now() + 55 * 60 * 1000; // 55 min (tokens last 60 min)
  return _token;
}

export async function apiPost<T>(path: string, body: object): Promise<T> {
  const token = await getToken();
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw { status: res.status, detail: err.detail ?? "Request failed" };
  }

  return res.json() as Promise<T>;
}

export async function apiGet<T>(path: string): Promise<T> {
  const token = await getToken();
  const res = await fetch(`${API_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw { status: res.status, detail: err.detail ?? "Request failed" };
  }

  return res.json() as Promise<T>;
}
