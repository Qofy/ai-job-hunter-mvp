export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json(
    {
      product: "JobPilot AI",
      version: "0.3.0",
      demoEnabled: process.env.NEXT_PUBLIC_ENABLE_DEMO === "true",
      legacyWorkspaceEnabled:
        process.env.NEXT_PUBLIC_LEGACY_WORKSPACE === "true",
    },
    { headers: { "Cache-Control": "no-store" } },
  );
}
