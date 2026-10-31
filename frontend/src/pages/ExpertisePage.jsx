import { useState, useEffect } from "react";
import { api } from "../api.js";
import { useRequest } from "../components/useRequest.js";
import ErrorBox from "../components/ErrorBox.jsx";

export default function ExpertisePage({ initialId }) {
  const [id, setId] = useState(initialId);
  const [state, run] = useRequest(api.expertise);
  useEffect(() => { if (initialId) run(initialId); }, []);

  const profile = state.data?.profile;
  const max = Math.max(1, ...(profile?.top_keywords.map((k) => k.count) ?? [1]));

  return (
    <>
      <h1 className="text-3xl">Expertise profile</h1>
      <p className="mb-6 mt-1.5 max-w-prose text-muted">
        Topics a professor publishes on most, extracted from their public papers. This can take a minute.
      </p>

      <div className="mb-5 rounded-lg border border-line bg-white p-5">
        <label htmlFor="eid" className="mb-1 block font-medium">Google Scholar ID or ORCID</label>
        <input id="eid" value={id} onChange={(e) => setId(e.target.value)} />
        <button
          disabled={state.loading || !id.trim()}
          onClick={() => run(id.trim())}
          className="mt-4 rounded-md bg-accent px-4 py-2.5 font-medium text-white disabled:cursor-wait disabled:opacity-60"
        >
          {state.loading ? "Analysing papers..." : "Show expertise"}
        </button>
      </div>

      <ErrorBox message={state.error} />

      {profile && (
        <section className="rounded-lg border border-line bg-white p-5">
          <h2 className="text-xl">{profile.professor_name}</h2>
          <p className="mb-3 text-muted">{profile.num_papers_analyzed} papers analysed</p>
          {profile.top_keywords.map((k) => (
            <div key={k.keyword} className="my-2 grid grid-cols-[110px_1fr_28px] items-center gap-3 md:grid-cols-[220px_1fr_32px]">
              <span>{k.keyword}</span>
              <div className="h-1.5 rounded bg-paper">
                <div className="h-full rounded bg-accent" style={{ width: `${(k.count / max) * 100}%` }} />
              </div>
              <span className="text-muted">{k.count}</span>
            </div>
          ))}
        </section>
      )}
    </>
  );
}