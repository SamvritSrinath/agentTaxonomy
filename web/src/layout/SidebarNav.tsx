import { NavLink } from "react-router-dom";

const NAV_ITEMS: Array<{ to: string; label: string; end?: boolean }> = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/runs", label: "Runs" },
  { to: "/prompts", label: "Prompts" },
  { to: "/instances", label: "Instances" },
  { to: "/jobs", label: "Jobs" },
  { to: "/exports", label: "Exports" },
  { to: "/settings", label: "Settings" }
];

export function SidebarNav() {
  return (
    <nav className="sidebar-nav">
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}
