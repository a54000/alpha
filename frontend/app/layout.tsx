import "./globals.css";
import "antd/dist/reset.css";
import Link from "next/link";
import { Activity, Briefcase, ClipboardList, FileSearch, Repeat2, Search, SlidersHorizontal } from "lucide-react";

export const metadata = {
  title: "Swing Research Cockpit",
  description: "Read-only dashboard for Sector Rotation ADX Rolling 10 research and paper trading"
};

const nav = [
  { href: "/", label: "Dashboard", icon: Activity },
  { href: "/recommendations", label: "Recommendations", icon: ClipboardList },
  { href: "/stock-analysis", label: "Stock Analysis", icon: Search },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/operations", label: "Operations", icon: SlidersHorizontal },
  { href: "/research/rolling-portfolio", label: "Rolling Portfolio", icon: Repeat2 },
  { href: "/research/trade-analysis", label: "Trade Analysis", icon: FileSearch }
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <aside className="sidebar">
            <p className="brand">Swing Research Cockpit</p>
            <nav className="nav">
              {nav.map((item) => {
                const Icon = item.icon;
                return (
                  <Link key={item.href} href={item.href}>
                    <Icon size={18} aria-hidden="true" />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          </aside>
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
