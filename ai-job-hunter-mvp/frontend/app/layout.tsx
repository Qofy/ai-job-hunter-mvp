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
    <html lang="en">
      {/* Browser extensions such as Grammarly add body attributes before hydration.
          Suppression is limited to this element; child mismatches remain visible. */}
      <body suppressHydrationWarning>
        <LocalAccountGate>{children}</LocalAccountGate>
      </body>
    </html>
  );
}
