export class LatestRequestGate {
  private generation = 0;

  begin(): number {
    this.generation += 1;
    return this.generation;
  }

  invalidate(): void {
    this.generation += 1;
  }

  isCurrent(requestId: number): boolean {
    return requestId === this.generation;
  }
}

type LatestHandlers<T> = {
  onSuccess: (value: T) => void;
  onError: (error: unknown) => void;
  onFinally?: () => void;
};

/** Commit an async result only while its request still owns the gate. */
export async function settleLatest<T>(
  gate: LatestRequestGate,
  requestId: number,
  request: () => Promise<T>,
  handlers: LatestHandlers<T>,
): Promise<void> {
  try {
    const value = await request();
    if (gate.isCurrent(requestId)) handlers.onSuccess(value);
  } catch (error) {
    if (gate.isCurrent(requestId)) handlers.onError(error);
  } finally {
    if (gate.isCurrent(requestId)) handlers.onFinally?.();
  }
}

/** Match a media event to the current source, including relative same-origin URLs. */
export function isCurrentMediaSource(
  currentSource: string,
  expectedSource: string,
  baseUrl: string,
): boolean {
  if (!currentSource || !expectedSource || !baseUrl) return false;
  try {
    return currentSource === new URL(expectedSource, baseUrl).href;
  } catch {
    return false;
  }
}
