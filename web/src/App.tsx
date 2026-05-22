import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./layout/AppShell";
import { DashboardPage } from "./pages/Dashboard";
import { ExportsPage } from "./pages/Exports";
import { InstanceDetailPage } from "./pages/InstanceDetail";
import { InstancesPage } from "./pages/Instances";
import { JobsPage } from "./pages/Jobs";
import { PromptDetailPage } from "./pages/PromptDetail";
import { PromptsPage } from "./pages/Prompts";
import { RunDetailRoute } from "./pages/RunDetail";
import { RunsPage } from "./pages/Runs";
import { SettingsPage } from "./pages/Settings";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="runs" element={<RunsPage />} />
        <Route path="runs/:runId" element={<RunDetailRoute />} />
        <Route path="prompts" element={<PromptsPage />} />
        <Route path="prompts/:promptId" element={<PromptDetailPage />} />
        <Route path="instances" element={<InstancesPage />} />
        <Route path="instances/:instanceId" element={<InstanceDetailPage />} />
        <Route path="jobs" element={<JobsPage />} />
        <Route path="exports" element={<ExportsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
