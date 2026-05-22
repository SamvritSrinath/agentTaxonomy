import { Outlet } from "react-router-dom";
import { OpenRouterSpendWidget } from "../components/OpenRouterSpendWidget";
import { SidebarNav } from "./SidebarNav";

export function AppShell() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-brand">
          <h1>Coding Agent Taxonomy</h1>
          <span>local evaluation workbench</span>
        </div>
        <OpenRouterSpendWidget />
      </header>
      <div className="app-body">
        <aside className="sidebar">
          <SidebarNav />
        </aside>
        <main className="app-outlet">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
