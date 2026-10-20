/** Only server-verified sessions unlock private tools; never use initDataUnsafe. */
export const OWNER_ID = "6265999542";
export const PUBLIC_SECTIONS = ["home", "post", "tools", "auth"] as const;
export function canOpenSection(
  section: string,
  owner: boolean | null,
): boolean {
  return (
    (PUBLIC_SECTIONS as readonly string[]).includes(section) || owner === true
  );
}
