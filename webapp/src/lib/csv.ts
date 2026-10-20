/** Quote every cell and neutralize spreadsheet formulas in exported labels/IDs. */
export function csvDocument(rows: readonly (readonly unknown[])[]): string {
  return (
    "\uFEFF" +
    rows
      .map((row) =>
        row
          .map((value) => {
            let cell = String(value ?? "");
            if (/^[\s]*[=+\-@]/.test(cell)) cell = "'" + cell;
            return `"${cell.replace(/"/g, '""')}"`;
          })
          .join(","),
      )
      .join("\r\n")
  );
}
export function downloadCsv(
  filename: string,
  rows: readonly (readonly unknown[])[],
) {
  const url = URL.createObjectURL(
    new Blob([csvDocument(rows)], { type: "text/csv;charset=utf-8" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
