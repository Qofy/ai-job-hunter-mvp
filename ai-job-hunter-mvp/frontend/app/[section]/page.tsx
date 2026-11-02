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
    "cv",
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
      "cv",
      "settings",
    ].includes(section)
  )
    notFound();
  return <Workspace section={section} />;
}
