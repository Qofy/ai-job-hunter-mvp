import type { ReactNode } from "react";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "./globals.css";
import LocalAccountGate from "../components/local-account";
export const metadata = {
  title: "JobPilot AI · Your next chapter",
  description: "A supervised workspace for your European job search.",
};
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    // Browser extensions can add attributes to html and body before hydration.
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <LocalAccountGate>{children}</LocalAccountGate>
      </body>
    </html>
  );
}
