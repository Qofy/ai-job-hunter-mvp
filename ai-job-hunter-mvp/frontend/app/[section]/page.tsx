import { notFound } from "next/navigation";
import Workspace from "../../components/workspace";
export function generateStaticParams() {
  return [
    "dashboard",
    "jobs",
    "approvals",
    "applications",
    "analytics",
    "profile",
    "settings",
  ].map((section) => ({ section }));
}
export default async function Page({
  params,
}: {
  params: Promise<{ section: string }>;
}) {
  const { section } = await params;
  if (
    ![
      "dashboard",
      "jobs",
      "approvals",
      "applications",
      "analytics",
      "profile",
      "settings",
    ].includes(section)
  )
    notFound();
  return <Workspace section={section} />;
}
