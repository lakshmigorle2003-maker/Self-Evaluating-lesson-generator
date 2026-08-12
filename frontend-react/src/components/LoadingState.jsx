import { useEffect, useState } from "react";

export default function LoadingState({ title, subtitle, showElapsed }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!showElapsed) return undefined;
    const startedAt = performance.now();
    const timer = setInterval(() => {
      setElapsed(Math.round((performance.now() - startedAt) / 1000));
    }, 500);
    return () => clearInterval(timer);
  }, [showElapsed]);

  return (
    <section className="loading-state">
      <div className="spinner" aria-hidden="true" />
      <h2>{title}</h2>
      <p>{subtitle}</p>
      {showElapsed && (
        <p className="elapsed">
          Elapsed: <span>{elapsed}s</span>
        </p>
      )}
    </section>
  );
}
