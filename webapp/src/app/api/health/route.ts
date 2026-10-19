export async function GET() {
  return Response.json({ status: "ok", service: "Videl0", uptime: process.uptime(), version: "2.0.0" });
}
