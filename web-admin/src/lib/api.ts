/**
 * The only module that talks to the backend. The operator session lives in an httpOnly cookie the browser attaches
 * itself, so no token ever passes through this code. Every request carries the CSRF header the API requires.
 */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly reference?: string,
  ) {
    super(message);
  }
}

type Params = Record<string, string | number | null | undefined>;

function withParams(path: string, params?: Params): string {
  if (!params) return path;
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") qs.set(key, String(value));
  }
  const text = qs.toString();
  return text ? `${path}?${text}` : path;
}

async function send(path: string, init: { method: string; body?: unknown; params?: Params }): Promise<Response> {
  return fetch(withParams(path, init.params), {
    method: init.method,
    credentials: "same-origin",
    headers: {
      "X-Requested-With": "predictax",
      ...(init.body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
  });
}

let refreshing: Promise<boolean> | null = null;
/** One refresh at a time, however many requests hit an expired token together. */
function refreshSession(): Promise<boolean> {
  refreshing ??= send("/api/admin/auth/refresh", { method: "POST" })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

async function failure(response: Response): Promise<ApiError> {
  let detail = "Something went wrong.";
  let reference: string | undefined;
  try {
    const body = await response.json();
    if (typeof body.detail === "string") detail = body.detail;
    else if (response.status === 422) detail = "Invalid request.";
    reference = body.reference;
  } catch {
    /* non-JSON error body: keep the generic message */
  }
  return new ApiError(response.status, detail, reference);
}

export async function api<T>(
  path: string,
  options: { method?: "GET" | "POST" | "PATCH"; body?: unknown; params?: Params } = {},
): Promise<T> {
  const init = { method: options.method ?? "GET", body: options.body, params: options.params };
  let response = await send(path, init);
  if (response.status === 401 && !path.startsWith("/api/admin/auth/") && (await refreshSession())) {
    response = await send(path, init);
  }
  if (!response.ok) throw await failure(response);
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}
