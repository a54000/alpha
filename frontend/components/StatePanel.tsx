export function ErrorState({ title = "Unable to load data", message }: { title?: string; message: string }) {
  return (
    <section className="panel">
      <h2 className="bad">{title}</h2>
      <p className="subtitle">{message}</p>
    </section>
  );
}

export function EmptyState({ title = "No data available", message }: { title?: string; message: string }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      <p className="subtitle">{message}</p>
    </section>
  );
}

export function LoadingState() {
  return (
    <section className="panel">
      <h2>Loading</h2>
      <p className="subtitle">Fetching the latest cockpit data.</p>
    </section>
  );
}
