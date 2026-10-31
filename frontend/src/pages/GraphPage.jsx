import { useState, useEffect } from "react";
import { api } from "../api.js";
import { useRequest } from "../components/useRequest.js";
import ErrorBox from "../components/ErrorBox.jsx";
import GraphView from "../components/GraphView.jsx";

const LEGEND = [
  ["bg-ink", "Reviewer"],
  ["bg-accent", "Paper"],
  ["bg-unverified", "Co-author"],
];

export default function GraphPage({ initialId }) {
  const [id, setId] = useState(initialId);
  const [state, run] = useRequest(api.graph);
  useEffect(() => { if (initialId) run(initialId); }, []);
  const d = state.data;

  return (
    <>
      <h1 className="text-3xl">Collaboration graph</h1>
      <p className="mb-6 mt-1.5 max-w-prose text-muted">
        A professor, their papers and co-authors. Hover a node to see its full title or name.
      </p>

      <div className="mb-5 rounded-lg border border-line bg-white p-5">
        <label htmlFor="gid" className="mb-1 block font-medium">Semantic Scholar ID, ORCID or Google Scholar ID</label>
        <input id="gid" value={id} onChange={(e) => setId(e.target.value)} />
        <button
          disabled={state.loading || !id.trim()}
          onClick={() => run(id.trim())}
          className="mt-4 rounded-md bg-accent px-4 py-2.5 font-medium text-white disabled:cursor-wait disabled:opacity-60"
        >
          {state.loading ? "Loading..." : "Show graph"}
        </button>
      </div>

      <ErrorBox message={state.error} />

      {d && (
        <>
          <div className="my-3 flex gap-5 text-sm">
            {LEGEND.map(([color, name]) => (
              <span key={name} className="flex items-center gap-1.5">
                <i className={`inline-block size-2.5 rounded-full ${color}`} />{name}
              </span>
            ))}
          </div>
          <div className="h-[620px] overflow-auto rounded-lg border border-line bg-white">
            <GraphView nodes={d.nodes} edges={d.edges} />
          </div>

          <section className="mt-5 rounded-lg border border-line bg-white p-5">
            <h2 className="mb-2 text-xl">Frequent collaborators</h2>
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-line text-left"><th className="py-2">Name</th><th className="py-2">Shared papers</th></tr>
              </thead>
              <tbody>
                {d.collaborators.slice(0, 25).map((c) => (
                  <tr key={c.s2_id} className="border-b border-line">
                    <td className="py-2">{c.name}</td><td className="py-2">{c.shared_papers}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </>
  );
}