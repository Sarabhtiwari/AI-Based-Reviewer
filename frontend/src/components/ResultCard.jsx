const STATUS = {
  conflict: { label: "Conflict of interest", edge: "border-l-conflict", text: "text-conflict" },
  unverified: { label: "Could not verify", edge: "border-l-unverified", text: "text-unverified" },
  clear: { label: "No conflict found", edge: "border-l-clear", text: "text-clear" },
};

export default function ResultCard({ match, onGraph }) {
  const pct = Math.max(0, Math.min(100, Math.round(match.similarity_score * 100)));
  const s = STATUS[match.conflict_status] || STATUS.unverified;

  return (
    <article className={`rounded-lg border border-line border-l-[6px] bg-white p-5 ${s.edge}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 className="text-lg">{match.professor_name}</h3>
        <span className={`text-sm font-semibold ${s.text}`}>{s.label}</span>
      </div>

      <div role="img" aria-label={`Similarity ${pct}%`} className="my-3 h-1.5 rounded bg-paper">
        <div className="h-full rounded bg-accent" style={{ width: `${pct}%` }} />
      </div>
      <p className="text-muted">Similarity {pct}% (best matching paper)</p>

      <p className="mt-3 font-medium">Closest papers</p>
      <ul className="list-disc pl-5">
        {match.matched_papers.map((t, i) => <li key={i}>{t}</li>)}
      </ul>

      {match.conflict_reasons.length > 0 && (
        <ul className="mt-3 list-disc pl-5">
          {match.conflict_reasons.map((r, i) => <li key={i}>{r}</li>)}
        </ul>
      )}

      {match.conflict_evidence?.length > 0 && (
        <table className="mt-3 w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-line text-left">
              <th className="py-1.5 pr-2">Co-author</th><th className="py-1.5 pr-2">Shared paper</th><th className="py-1.5">Year</th>
            </tr>
          </thead>
          <tbody>
            {match.conflict_evidence.map((e, i) => (
              <tr key={i} className="border-b border-line">
                <td className="py-1.5 pr-2">{e.author}</td><td className="py-1.5 pr-2">{e.paper}</td><td className="py-1.5">{e.year ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <button
        onClick={() => onGraph(match.scholar_id)}
        className="mt-4 rounded-md bg-accent-soft px-3 py-1.5 text-sm text-accent"
      >
        View collaboration graph
      </button>
    </article>
  );
}