import { useState } from "react";

export default function Sidebar({ health, runs, activeRunId, onSelectRun, onGenerate, generating }) {
  const [topic, setTopic] = useState("");
  const [maxRetries, setMaxRetries] = useState("");
  const [generatorModel, setGeneratorModel] = useState("");
  const [evaluatorModel, setEvaluatorModel] = useState("");
  const [useMemory, setUseMemory] = useState(true);
  const [saveExample, setSaveExample] = useState(true);

  function handleSubmit(event) {
    event.preventDefault();
    const payload = {
      topic: topic.trim(),
      save_as_example: saveExample,
      use_memory: useMemory,
    };
    if (maxRetries !== "") payload.max_retries = Number(maxRetries);
    if (generatorModel.trim()) payload.generator_model = generatorModel.trim();
    if (evaluatorModel.trim()) payload.evaluator_model = evaluatorModel.trim();
    onGenerate(payload);
  }

  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">LF</span>
        <div>
          <h1>Lesson Forge</h1>
          <p>Self-evaluating lesson generator</p>
        </div>
      </div>

      <form className="generate-form" onSubmit={handleSubmit}>
        <label className="field">
          <span className="field-label">Topic</span>
          <textarea
            rows={2}
            placeholder='e.g. Introduction to RAG (Retrieval-Augmented Generation)'
            required
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
          />
        </label>

        <details className="advanced">
          <summary>Advanced options</summary>

          <label className="field">
            <span className="field-label">Max retries</span>
            <input
              type="number"
              min={0}
              max={10}
              placeholder="default"
              value={maxRetries}
              onChange={(e) => setMaxRetries(e.target.value)}
            />
          </label>

          <label className="field">
            <span className="field-label">Generator model</span>
            <input
              type="text"
              placeholder="default"
              value={generatorModel}
              onChange={(e) => setGeneratorModel(e.target.value)}
            />
          </label>

          <label className="field">
            <span className="field-label">Evaluator model</span>
            <input
              type="text"
              placeholder="default"
              value={evaluatorModel}
              onChange={(e) => setEvaluatorModel(e.target.value)}
            />
          </label>

          <label className="field field-checkbox">
            <input type="checkbox" checked={useMemory} onChange={(e) => setUseMemory(e.target.checked)} />
            <span>Use cross-run pitfall memory</span>
          </label>

          <label className="field field-checkbox">
            <input type="checkbox" checked={saveExample} onChange={(e) => setSaveExample(e.target.checked)} />
            <span>Mirror into examples/</span>
          </label>
        </details>

        <button type="submit" className="btn-primary" disabled={generating}>
          <span className="btn-label">Generate lesson</span>
        </button>
      </form>

      <div className="status-block">
        <span className={`status-dot ${healthDotClass(health)}`} />
        <span>{healthText(health)}</span>
      </div>

      <div className="runs-panel">
        <h2>Past runs</h2>
        <ul className="runs-list">
          {runs.length === 0 && <li className="runs-empty">No runs yet</li>}
          {runs.map((run) => (
            <li
              key={run.run_id}
              className={`run-item ${run.run_id === activeRunId ? "active" : ""}`}
              onClick={() => onSelectRun(run.run_id)}
            >
              <span className="run-item-topic">{run.topic}</span>
              <span className="run-item-meta">
                <span className={`run-item-pill ${run.final_passed ? "pass" : "fail"}`}>
                  {run.final_passed ? "pass" : "best-effort"}
                </span>
                <span>
                  {run.total_attempts} attempt{run.total_attempts === 1 ? "" : "s"}
                </span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

function healthDotClass(health) {
  if (health === "loading" || health === null) return "";
  if (health === "unreachable") return "error";
  return health.api_key_configured ? "ok" : "error";
}

function healthText(health) {
  if (health === "loading" || health === null) return "Checking backend…";
  if (health === "unreachable") return "Backend unreachable";
  return health.api_key_configured
    ? `${health.generator_model} → ${health.evaluator_model}`
    : "No API key configured on the backend";
}
