/** Server-only owner identity. Never import this module from client components. */
export function configuredOwnerId(): string {
  const value = process.env.OWNER_ID?.trim() ?? "";
  return /^[1-9][0-9]{0,19}$/.test(value) ? value : "";
}
