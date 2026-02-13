export interface NormalizedListResponse<T> {
  results: T[];
  count?: number;
  next?: string | null;
  previous?: string | null;
}

interface DrfPaginatedLike<T> {
  results?: unknown;
  count?: unknown;
  next?: unknown;
  previous?: unknown;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function normalizeListResponse<T>(response: unknown): NormalizedListResponse<T> {
  if (Array.isArray(response)) {
    return {
      results: response as T[],
      count: response.length,
      next: null,
      previous: null,
    };
  }

  if (!isObject(response)) {
    return {
      results: [],
      count: 0,
      next: null,
      previous: null,
    };
  }

  const paginated = response as DrfPaginatedLike<T>;
  const results = Array.isArray(paginated.results) ? (paginated.results as T[]) : [];
  const parsedCount =
    typeof paginated.count === "number" ? paginated.count : results.length;

  return {
    results,
    count: parsedCount,
    next:
      typeof paginated.next === "string" || paginated.next === null
        ? paginated.next
        : null,
    previous:
      typeof paginated.previous === "string" || paginated.previous === null
        ? paginated.previous
        : null,
  };
}
