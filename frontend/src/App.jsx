import { useEffect, useState } from "react";
import { Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import NewRunPage from "./pages/NewRunPage";
import RunPage from "./pages/RunPage";

const STORAGE_KEY = "sct-recent-runs";

function loadRecentRuns() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export default function App() {
  const [recentRuns, setRecentRuns] = useState(loadRecentRuns);

  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(recentRuns));
  }, [recentRuns]);

  function handleRunCreated(run) {
    setRecentRuns((prev) => [{ runId: run.run_id, config: run.config }, ...prev].slice(0, 20));
  }

  return (
    <div className="app-shell">
      <Sidebar recentRuns={recentRuns} />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<NewRunPage onRunCreated={handleRunCreated} />} />
          <Route path="/runs/:runId" element={<RunPage />} />
        </Routes>
      </main>
    </div>
  );
}
