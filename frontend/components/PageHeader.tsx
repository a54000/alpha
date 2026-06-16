export function PageHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="topbar">
      <div>
        <h1 className="title">{title}</h1>
        <p className="subtitle">{subtitle}</p>
      </div>
      <span className="badge">Read-only</span>
    </div>
  );
}
