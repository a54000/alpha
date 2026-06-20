import "./globals.css";
import "antd/dist/reset.css";
import { Activity } from "lucide-react";
import { SidebarNav } from "@/components/SidebarNav";

export const metadata = {
  title: "SectorEdge 10",
  description: "Read-only dashboard for recommendations, portfolio review, and paper trading"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <aside className="sidebar">
            <div className="brand-block">
              <div className="brand">
                <Activity size={17} aria-hidden="true" />
                <span>SectorEdge 10</span>
              </div>
            </div>
            <SidebarNav />
          </aside>
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
