import { useState } from "react";
import { api, splitList } from "../api.js";
import { useRequest } from "../components/useRequest.js";
import ErrorBox from "../components/ErrorBox.jsx";

const panel = "mb-5 rounded-lg border border-line bg-white p-5";
const label = "mb-1 mt-3.5 block font-medium";
const primary = "mt-4 rounded-md bg-accent px-4 py-2.5 font-medium text-white disabled:cursor-wait disabled:opacity-60";
const ghost = "rounded-md bg-accent-soft px-3 py-1.5 text-sm text-accent";

export default function IndexPage({ go }) {
  const [single, setSingle] = useState("");
  const [batch, setBatch] = useState("");
  const [one, runOne] = useRequest(api.indexProfessor);
  const [many, runMany] = useRequest(api.indexBatch);
  const ids = splitList(batch);

  return (
    <>
      <h1 className="text-3xl">Index professors</h1>
      <p className="mb-6 mt-1.5 max-w-prose text-muted">
        Add reviewers to the pool with a Google Scholar ID or an ORCID. Indexing stores their paper vectors
        and co-author graph. Batch indexing is slow because of API rate limits.
      </p>

      <section className={panel}>
        <h2 className="text-xl">One professor</h2>
        <label htmlFor="one" className={label}>Google Scholar ID or ORCID</label>
        <input id="one" value={single} onChange={(e) => setSingle(e.target.value)} placeholder="0000-0002-1825-0097" />
        <button className={primary} disabled={one.loading || !single.trim()} onClick={() => runOne(single.trim())}>
          {one.loading ? "Indexing..." : "Index professor"}
        </button>
        <ErrorBox message={one.error} />
        {one.data && (
          <div className="mt-4">
            Indexed <strong>{one.data.professor_name}</strong>: {one.data.papers_indexed} papers
            {one.data.match_percent != null && ` (${one.data.match_percent}% title match)`}.{" "}
            {one.data.graph_error ? (
              <span className="text-muted">Graph not updated: {one.data.graph_error}</span>
            ) : (
              <>
                {one.data.graph?.coauthors} co-authors in graph.{" "}
                <button className={ghost} onClick={() => go("graph", one.data.scholar_id)}>View graph</button>
              </>
            )}
          </div>
        )}
      </section>

      <section className={panel}>
        <h2 className="text-xl">Several professors</h2>
        <label htmlFor="many" className={label}>IDs <span className="font-normal text-muted">(comma or line separated)</span></label>
        <textarea id="many" rows={5} value={batch} onChange={(e) => setBatch(e.target.value)} />
        <button className={primary} disabled={many.loading || !ids.length} onClick={() => runMany(ids)}>
          {many.loading ? "Indexing, please wait..." : `Index ${ids.length || ""} professors`}
        </button>
        <ErrorBox message={many.error} />
        {many.data && (
          <table className="mt-4 w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-line text-left">
                <th className="py-2 pr-2">ID</th><th className="py-2 pr-2">Result</th><th className="py-2 pr-2">Papers</th><th className="py-2">Co-authors</th>
              </tr>
            </thead>
            <tbody>
              {many.data.results.map((r) => (
                <tr key={r.scholar_id} className="border-b border-line">
                  <td className="py-2 pr-2">{r.scholar_id}</td>
                  <td className="py-2 pr-2">
                    {r.status === "success" ? (
                      <>{r.professor_name}{r.graph_error && <span className="text-muted"> (graph failed)</span>}</>
                    ) : (
                      <span className="text-conflict">{r.error}</span>
                    )}
                  </td>
                  <td className="py-2 pr-2">{r.papers_indexed ?? "-"}</td>
                  <td className="py-2">{r.graph_coauthors ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}