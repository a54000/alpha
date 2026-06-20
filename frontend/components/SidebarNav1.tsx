"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Briefcase,
  ClipboardList,
  FileSearch,
  LayoutDashboard,
  Repeat2,
  Search,
  SlidersHorizontal
} from "lucide-react";

const navGroups = [
  {
    label: "Overview",
    items: [{ href: "/", label: "Dashboard", icon: LayoutDashboard }]
  },
  {
    label: "Live Strategy",
    items: [
      { href: "/recommendations", label: "Recommendations", icon: ClipboardList, badge: "Live" },
      { href: "/portfolio", label: "Portfolio", icon: Briefcase }
    ]
  },
  {
    label: "Research & Operations",
    items: [
      { href: "/stock-analysis", label: "Stock Analysis", icon: Search },
      { href: "/research/rolling-portfolio", label: "Rolling Portfolio", icon: Repeat2 },
      { href: "/research/trade-analysis", label: "Trade Analysis", icon: FileSearch },
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
        <div className="nav-group" key={group.label}>
          <p>{group.label}</p>
          {group.items.map((item) => {
            const Icon = item.icon;
            return (
              <Link key={item.href} href={item.href} className={isActive(pathname, item.href) ? "nav-active" : undefined}>
                <Icon size={17} aria-hidden="true" />
                <span>{item.label}</span>
                {"badge" in item ? <small>{item.badge}</small> : null}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}
