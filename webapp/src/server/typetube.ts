import { createClient, type TypeTube } from "typetube";

const DEFAULT_HOST = "sg.clusters.typetube.xyz:8443";
const REQUEST_TIMEOUT_MS = 10_000;

declare global {
  // Reuse one TAP connection across requests in a warm Node.js worker.
  // eslint-disable-next-line no-var
  var __videlTypeTubeClient: TypeTube | undefined;
}

export function typeTubeEnabled(): boolean {
  return process.env.TYPETUBE_ENABLED !== "0";
}

export function getTypeTubeClient(): TypeTube {
  if (!typeTubeEnabled()) throw new Error("TypeTube is disabled");
  if (globalThis.__videlTypeTubeClient) return globalThis.__videlTypeTubeClient;

  const host = (process.env.TYPETUBE_HOST || DEFAULT_HOST).trim();
  if (!/^[A-Za-z0-9.-]+(?::[0-9]{1,5})?$/.test(host)) {
    throw new Error("Invalid TypeTube host configuration");
  }
  const separator = host.lastIndexOf(":");
  if (separator !== -1) {
    const port = Number(host.slice(separator + 1));
    if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error("Invalid TypeTube host configuration");
  }

  globalThis.__videlTypeTubeClient = createClient({
    host,
    apiKey: process.env.TYPETUBE_API_KEY || undefined,
    timeoutMs: REQUEST_TIMEOUT_MS,
  });
  return globalThis.__videlTypeTubeClient;
}
