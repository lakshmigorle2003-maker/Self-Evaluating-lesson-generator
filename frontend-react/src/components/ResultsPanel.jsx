import { useState } from "react";
import ReactMarkdown from "react-markdown";

export default function ResultsPanel({ result }) {
  const [activeTab, setActiveTab] = useState("lesson");
  const finalAttempt = result.attempts[result.attempts.length - 1];
  const verdicts = finalAttempt ? finalAttempt.verdicts : [];
  const passedCount = verdicts.filter((v) => v.passed).length;

  return (
    <section className="results-state">
      <header className="results-header">
        <div className="results-heading">
          <span className={`badge ${result.final_passed ? "pass" : "fail"}`}>
            {result.final_passed ? "Passed" : "Best effort"}
          </span>
          <h2>{result.topic}</h2>
        </div>
        <dl className="results-meta">
          <div>
            <dt>Run</dt>
            <dd>{result.run_id}</dd>
          </div>
          <div>
            <dt>Attempts</dt>
            <dd>
              {result.total_attempts} (final #{result.final_attempt_number})
            </dd>
          </div>
          <div>
            <dt>Generator</dt>
            <dd>{result.generator_model}</dd>
          </div>
          <div>
            <dt>Evaluator</dt>
            <dd>{result.evaluator_model}</dd>
          </div>
        </dl>
      </header>

      <nav className="tabs">
        {[
          ["lesson", "Lesson"],
          ["report", "Rubric report"],
          ["history", "Attempt history"],
        ].map(([key, label]) => (
          <button
            key={key}
            className={`tab-button ${activeTab === key ? "active" : ""}`}
            onClick={() => setActiveTab(key)}
          >
            {label}
          </button>
        ))}
      </nav>

      {activeTab === "lesson" && (
        <div className="tab-panel">
          <article className="lesson-content">
            <ReactMarkdown>{result.lesson_markdown}</ReactMarkdown>
          </article>
        </div>
      )}

      {activeTab === "report" && (
        <div className="tab-panel">
          <div className="rubric-summary">
            <div className="rubric-stat">
              <span className="rubric-stat-value">
                {passedCount}/{verdicts.length}
              </span>
              <span className="rubric-stat-label">Checkpoints passed (final attempt)</span>
            </div>
            <div className="rubric-stat">
              <span className="rubric-stat-value">{result.final_attempt_number}</span>
              <span className="rubric-stat-label">Attempts used</span>
            </div>
          </div>
          <div className="rubric-grid">
            {verdicts
              .slice()
              .sort((a, b) => a.checkpoint_id.localeCompare(b.checkpoint_id, undefined, { numeric: true }))
              .map((v) => (
                <div key={v.checkpoint_id} className={`rubric-card ${v.passed ? "pass" : "fail"}`}>
                  <div className="rubric-card-head">
                    <span className="rubric-card-icon">{v.passed ? "✓" : "✗"}</span>
                    <span className="rubric-card-id">{v.checkpoint_id}</span>
                  </div>
                  <p className="rubric-card-question">{v.question}</p>
                  <p className="rubric-card-reason">{v.reason}</p>
                </div>
              ))}
          </div>
        </div>
      )}

      {activeTab === "history" && (
        <div className="tab-panel">
          <ol className="attempt-timeline">
            {result.attempts.map((attempt) => (
              <li key={attempt.attempt_number} className={`attempt-item ${attempt.passed ? "pass" : "fail"}`}>
                <div className="attempt-item-head">
                  <h3>Attempt {attempt.attempt_number}</h3>
                  <span className={`badge ${attempt.passed ? "pass" : "fail"}`}>
                    {attempt.passed ? "Passed" : "Failed"}
                  </span>
                </div>
                <div className="attempt-item-body">
                  <p>{attempt.overall_impression}</p>
                  {attempt.failed_checkpoint_ids.length > 0 && (
                    <>
                      <p>Failed checkpoints:</p>
                      <ul className="attempt-failed-list">
                        {attempt.failed_checkpoint_ids.map((id) => (
                          <li key={id}>
                            <code>{id}</code>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                  {attempt.feedback_given_to_next_attempt && (
                    <div className="attempt-feedback">{attempt.feedback_given_to_next_attempt}</div>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
