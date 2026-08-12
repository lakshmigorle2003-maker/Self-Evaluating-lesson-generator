export default function EmptyState() {
  return (
    <section className="empty-state">
      <div className="empty-illustration" aria-hidden="true">
        <svg viewBox="0 0 120 120" width="96" height="96">
          <circle cx="60" cy="60" r="54" className="empty-ring" />
          <path d="M40 76 L40 44 L60 34 L80 44 L80 76 L60 86 Z" className="empty-shape" />
          <path d="M40 44 L60 54 L80 44" className="empty-shape-line" />
          <line x1="60" y1="54" x2="60" y2="86" className="empty-shape-line" />
        </svg>
      </div>
      <h2>No lesson generated yet</h2>
      <p>
        Enter a topic on the left and click <strong>Generate lesson</strong>. The system will write a beginner
        lesson, grade it against a 13-point hard pass/fail rubric, and automatically regenerate on failure.
      </p>
    </section>
  );
}
