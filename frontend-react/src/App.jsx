import { useCallback, useEffect, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import EmptyState from "./components/EmptyState.jsx";
import LoadingState from "./components/LoadingState.jsx";
import ResultsPanel from "./components/ResultsPanel.jsx";
import { getHealth, listRuns, getRun, generateLesson } from "./api.js";

export default function App() {
  const [health, setHealth] = useState("loading");
  const [runs, setRuns] = useState([]);
  const [view, setView] = useState({ kind: "empty" });
  const [generating, setGenerating] = useState(false);

  const refreshHealth = useCallback(async () => {
    try {
      setHealth(await getHealth());
    } catch {
      setHealth("unreachable");
    }
  }, []);

  const refreshRuns = useCallback(async () => {
    try {
      setRuns(await listRuns());
    } catch {
      // Non-fatal -- past runs are a convenience, not required for generation.
    }
  }, []);

  useEffect(() => {
    refreshHealth();
    refreshRuns();
  }, [refreshHealth, refreshRuns]);

  async function handleGenerate(payload) {
    setGenerating(true);
    setView({ kind: "loading", title: "Generating & grading…", subtitle: "This runs several real model calls and can take a minute or two.", showElapsed: true });
    try {
      const result = await generateLesson(payload);
      setView({ kind: "result", result });
      await refreshRuns();
    } catch (err) {
      setView({ kind: "error", message: err.message });
    } finally {
      setGenerating(false);
    }
  }

  async function handleSelectRun(runId) {
    setView({ kind: "loading", title: "Loading run…", subtitle: "", showElapsed: false });
    try {
      const result = await getRun(runId);
      setView({ kind: "result", result });
    } catch (err) {
      setView({ kind: "error", message: err.message });
    }
  }

  return (
    <div className="app-shell">
      <Sidebar
        health={health}
        runs={runs}
        activeRunId={view.kind === "result" ? view.result.run_id : null}
        onSelectRun={handleSelectRun}
        onGenerate={handleGenerate}
        generating={generating}
      />
      <main className="main-panel">
        {view.kind === "empty" && <EmptyState />}
        {view.kind === "loading" && (
          <LoadingState title={view.title} subtitle={view.subtitle} showElapsed={view.showElapsed} />
        )}
        {view.kind === "error" && (
          <section className="error-state">
            <h2>Something went wrong</h2>
            <p>{view.message}</p>
          </section>
        )}
        {view.kind === "result" && <ResultsPanel result={view.result} />}
      </main>
    </div>
  );
}
