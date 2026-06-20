"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Briefcase,
  ClipboardList,
  FileSearch,
  Gauge,
  LayoutDashboard,
  Orbit,
  Repeat2,
  Search,
  SlidersHorizontal
} from "lucide-react";

const navGroups = [
  {
    label: "Overview",
    items: [
      { href: "/", label: "Dashboard", icon: LayoutDashboard },
      { href: "/market-lens", label: "Market Lens", icon: Gauge },
      { href: "/market-breadth", label: "Market Breadth", icon: Gauge },
      { href: "/research/sector-rotation", label: "Sector Rotation", icon: Orbit }
    ]
  },
  {
    label: "Stock Selection",
    items: [
      { href: "/recommendations", label: "Recommendations", icon: ClipboardList, badge: "Live" },
      { href: "/stock-analysis", label: "Stock Analysis", icon: Search }
    ]
  },
  {
    label: "Portfolio",
    items: [
      { href: "/portfolio", label: "Portfolio", icon: Briefcase },
      { href: "/research/rolling-portfolio", label: "Rolling Portfolio", icon: Repeat2 },
      { href: "/research/trade-analysis", label: "Trade Analysis", icon: FileSearch }
    ]
  },
  {
    label: "Operations",
    items: [
      { href: "/research", label: "Research", icon: FileSearch },
      { href: "/operations", label: "Pipeline", icon: SlidersHorizontal }
    ]
  }
];

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === href : pathname.startsWith(href);
}

export function SidebarNav() {
  const pathname = usePathname() ?? "/";

  return (
    <nav className="nav">
      {navGroups.map((group) => (
        <div key={group.label}>
          <div className="nav-group">
            <p>{group.label}</p>
            {group.items.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={isActive(pathname, item.href) ? "nav-active" : undefined}
                >
                  <Icon size={17} aria-hidden="true" />
                  <span>{item.label}</span>
                  {"badge" in item ? <small>{item.badge}</small> : null}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}
