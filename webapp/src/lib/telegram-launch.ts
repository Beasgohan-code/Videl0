/** Launch data is untrusted until the backend verifies Telegram's signature. */
export function telegramLaunchData(
  sdkData: unknown,
  search: string,
  hash: string,
): string {
  if (
    typeof sdkData === "string" &&
    sdkData.length > 0 &&
    sdkData.length <= 8192
  )
    return sdkData;
  for (const part of [hash.replace(/^#/, ""), search.replace(/^\?/, "")]) {
    const data = new URLSearchParams(part).get("tgWebAppData");
    if (data && data.length <= 8192) return data;
  }
  return "";
}
