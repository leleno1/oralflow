import "./styles.css";

const boundaries = [
  "Versioned contracts",
  "Offline validation",
  "Deterministic mock adapter",
  "No workflow runtime",
] as const;

export function App() {
  return (
    <main className="shell">
      <section className="status-card" aria-labelledby="page-title">
        <p className="eyebrow">ORALFLOW · M0</p>
        <h1 id="page-title">Engineering Harness</h1>
        <p className="summary">
          The project is freezing contracts and verification gates before
          workflow execution or product UI development begins.
        </p>
        <ul>
          {boundaries.map((boundary) => (
            <li key={boundary}>{boundary}</li>
          ))}
        </ul>
        <p className="status">
          <span aria-hidden="true" />
          External models disabled
        </p>
      </section>
    </main>
  );
}
