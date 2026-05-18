/**
 * API client.
 *
 * - All requests carry credentials so the archive_session cookie is
 *   sent automatically. Login (via /auth/dev/login) sets the cookie;
 *   subsequent requests just work.
 * - Unwraps the {data, meta} envelope: api<T>(...) returns T directly.
 * - 4xx/5xx throw an Error with a `.status` and `.detail` so callers
 *   can branch on it.
 */

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message?: string) {
    super(message || `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

export interface Envelope<T> {
  data: T;
  meta: {
    page?: number;
    page_size?: number;
    total?: number;
    extra?: Record<string, unknown>;
  };
}

interface Opts {
  method?: "GET" | "POST" | "PATCH" | "DELETE" | "PUT";
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
}

function qs(query?: Opts["query"]): string {
  if (!query) return "";
  const parts: string[] = [];
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null || v === "") continue;
    parts.push(`${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  }
  return parts.length ? "?" + parts.join("&") : "";
}

/**
 * Call the API. Returns parsed JSON envelope (so callers can read
 * either .data or .meta), or null if the server returned 204.
 */
export async function apiRaw<T = unknown>(
  path: string,
  opts: Opts = {},
): Promise<Envelope<T> | null> {
  const url = `/api/v1${path}${qs(opts.query)}`;
  const init: RequestInit = {
    method: opts.method ?? "GET",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
  };
  if (opts.body !== undefined) {
    init.body = JSON.stringify(opts.body);
  }
  const res = await fetch(url, init);
  if (res.status === 204) return null;
  let json: unknown = null;
  try { json = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    throw new ApiError(
      res.status,
      json,
      (json && typeof json === "object" && "detail" in json)
        ? String((json as Record<string, unknown>).detail)
        : `HTTP ${res.status}`,
    );
  }
  return json as Envelope<T>;
}

/**
 * Convenience: returns .data directly, raises if the server returned
 * something without a .data field (shouldn't happen on success paths).
 */
export async function api<T = unknown>(path: string, opts: Opts = {}): Promise<T> {
  const env = await apiRaw<T>(path, opts);
  if (env === null) {
    // 204 No Content — caller should use apiRaw and handle null
    throw new ApiError(204, null, "expected body, got 204");
  }
  return env.data;
}

// =====================================================================
// API resource types — minimal subset matching the backend schemas
// =====================================================================

export interface Author {
  id: number;
  slug: string;
  name: string;
  avatar_letter?: string | null;
  avatar_color?: string | null;
  role?: string | null;
}

export interface CivStats {
  entries: number;
  inquisitions: number;
  people: number;
  years: number;
}

export interface CivilizationSummary {
  slug: string;
  name: string;
  status: string;
  galaxy?: string | null;
  founded?: string | null;
  ended?: string | null;
  tagline?: string | null;
  color_primary: string;
  color_secondary: string;
  stats: CivStats;
}

export interface CivilizationDetail extends CivilizationSummary {
  description?: string | null;
  founded_year?: number | null;
  ended_year?: number | null;
}

export interface CoverageItem {
  kind: "story" | "inquisition";
  id: number;
  slug?: string;
  doctype?: string;
  headline: string;
  deck?: string | null;
  beat?: string | null;
  published_at?: string | null;
  started_at?: string | null;
  numeral?: string | null;
  state?: string | null;
  author?: Author | null;
}

export interface StorySummary {
  id: number;
  slug: string;
  doctype: "brief" | "feature";
  headline: string;
  deck?: string | null;
  beat?: string | null;
  civs: string[];
  author: Author;
  published_at: string;
  read_minutes?: number | null;
}

export interface StoryDetail extends StorySummary {
  body: string;
}

export interface InquisitionSummary {
  id: number;
  slug: string;
  numeral: string;
  title: string;
  subtitle?: string | null;
  deck?: string | null;
  state: string;
  progress: number;
  sources_count: number;
  started_at: string;
  closed_at?: string | null;
  authors: Author[];
  civs: string[];
}

export interface InquisitionDetail extends InquisitionSummary {
  body: string;
}

export interface TimelineEntry {
  kind: string;  // event / story / inquisition / civ-founded / civ-ended
  date: string;
  year?: number | null;
  title: string;
  slug?: string | null;
  id?: number | null;
  doctype?: string | null;
  civs: string[];
}

export interface SearchHit {
  kind: string;  // story / inquisition / civilization / person
  id: number;
  slug: string;
  title: string;
  snippet?: string | null;
}

export interface PersonDetail {
  slug: string;
  name: string;
  discord_username?: string | null;
  civ_slug?: string | null;
  role_in_civ?: string | null;
  bio?: string | null;
}

export interface DraftCoauthor {
  user_id: number;
  slug: string;
  name: string;
  avatar_letter?: string | null;
  avatar_color?: string | null;
}

export interface DraftSummary {
  id: number;
  doctype: "brief" | "feature" | "inquisition";
  headline?: string | null;
  deck?: string | null;
  beat?: string | null;
  numeral?: string | null;
  status: "draft" | "in_review" | "returned" | "ready" | "published";
  author: Author;
  coauthors: DraftCoauthor[];
  civs: string[];
  last_edited_at: string;
  created_at: string;
  reviewed_by_id?: number | null;
  reviewed_at?: string | null;
}

export interface DraftDetail extends DraftSummary {
  body: string;
  published_as_story_id?: number | null;
  published_as_inquisition_id?: number | null;
}

export interface CommentDetail {
  id: number;
  draft_id: number;
  author: Author;
  body: string;
  quoted_text?: string | null;
  created_at: string;
}

export interface NotificationDetail {
  id: number;
  type: string;
  title: string;
  body?: string | null;
  link?: string | null;
  related_draft_id?: number | null;
  related_user_id?: number | null;
  is_read: boolean;
  created_at: string;
}

export interface MeUser {
  id: number;
  discord_username: string;
  display_name: string;
  avatar_letter?: string | null;
  avatar_color?: string | null;
  civ_slug?: string | null;
  beat?: string | null;
  base_role: string;
  is_editor: boolean;
  is_admin: boolean;
  /** True if the row has password_hash set. */
  has_password?: boolean;
  /** True if the user is admin or editor BUT no password is set yet.
   *  The server will 403 their privileged actions until they set one. */
  needs_password?: boolean;
}

export interface DevUser {
  id: number;
  slug: string;
  name: string;
  avatar_letter?: string | null;
  avatar_color?: string | null;
  civ_slug?: string | null;
  beat?: string | null;
  base_role: string;
  is_editor: boolean;
  is_admin: boolean;
}
