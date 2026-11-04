import { useState } from "react";
import { api, splitList } from "../api.js";
import { useRequest } from "../components/useRequest.js";
import ErrorBox from "../components/ErrorBox.jsx";
import ResultCard from "../components/ResultCard.jsx";

const label = "mb-1 mt-3.5 block font-medium";
const hint = "font-normal text-muted";

// The backend may return plain strings or objects; show either safely.
const show = (x) => (typeof x === "string" ? x : JSON.stringify(x));

export default function MatchPage({ go }) {
  const [form, setForm] = useState({
    title: "",
    abstract: "",
    top_k: 5,
    ids: "",
    names: "",
    institutions: "",
    orcids: "",
  });
  const [state, run] = useRequest(api.matchReviewers);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = (e) => {
    e.preventDefault();
    run({
      title: form.title,
      abstract: form.abstract,
      top_k: Number(form.top_k) || 5,
      author_ids: splitList(form.ids),
      author_names: splitList(form.names),
      author_institutions: splitList(form.institutions),
      author_orcids: splitList(form.orcids),
    });
  };

  const data = state.data;
  const unresolved = data?.author_resolution?.filter((a) => !a.authorId) ?? [];
  const warnings = data?.warnings ?? [];
  const instUsed = data?.author_institutions_used ?? [];
  const noInstitutionInput = !form.institutions.trim() && !form.orcids.trim();

  return (
    <>
      <h1 className="text-3xl">Match reviewers</h1>
      <p className="mb-6 mt-1.5 max-w-prose text-muted">
        Find reviewers for a confidential paper. The title and abstract are embedded locally and never leave
        your machine. Only author names, IDs, ORCIDs and institutions are used for the conflict check.
      </p>

      <form onSubmit={submit} className="mb-5 rounded-lg border border-line bg-white p-5">
        <label htmlFor="title" className={label}>Paper title</label>
        <input id="title" required value={form.title} onChange={set("title")} />

        <label htmlFor="abstract" className={label}>Abstract <span className={hint}>(optional, improves matching)</span></label>
        <textarea id="abstract" rows={6} value={form.abstract} onChange={set("abstract")} />

        <h2 className="mt-6 text-xl">Paper authors <span className={hint}>(for the conflict check)</span></h2>
        <p className="mt-1 max-w-prose text-sm text-muted">
          Give the authors as Semantic Scholar IDs (exact) or names (best effort). Give their institutions as text,
          or their ORCIDs so the institutions are read from ORCID. Without institutions, the same-institution check
          is skipped and a reviewer cannot be marked clear.
        </p>

        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label htmlFor="ids" className={label}>Author IDs <span className={hint}>(Semantic Scholar, exact)</span></label>
            <textarea id="ids" rows={3} value={form.ids} onChange={set("ids")} placeholder="One per line or comma separated" />
          </div>
          <div>
            <label htmlFor="names" className={label}>Author names <span className={hint}>(fallback, searched by name)</span></label>
            <textarea id="names" rows={3} value={form.names} onChange={set("names")} />
          </div>
          <div>
            <label htmlFor="institutions" className={label}>Author institutions <span className={hint}>(text)</span></label>
            <textarea
              id="institutions"
              rows={3}
              value={form.institutions}
              onChange={set("institutions")}
              placeholder="e.g. IIT Bombay (one per line or comma separated)"
            />
          </div>
          <div>
            <label htmlFor="orcids" className={label}>Author ORCIDs <span className={hint}>(institutions read from ORCID)</span></label>
            <textarea
              id="orcids"
              rows={3}
              value={form.orcids}
              onChange={set("orcids")}
              placeholder="0000-0000-0000-0000"
            />
          </div>
        </div>

        <label htmlFor="k" className={label}>Reviewers to return</label>
        <input id="k" type="number" min={1} max={50} value={form.top_k} onChange={set("top_k")} className="!w-24" />

        {noInstitutionInput && (
          <p className="mt-4 rounded border-l-4 border-unverified bg-amber-50 px-4 py-2 text-sm">
            No institutions or ORCIDs entered: results can be "conflict" or "could not verify", never "no conflict found".
          </p>
        )}

        <button disabled={state.loading} className="mt-5 rounded-md bg-accent px-4 py-2.5 font-medium text-white disabled:cursor-wait disabled:opacity-60">
          {state.loading ? "Matching..." : "Find reviewers"}
        </button>
      </form>

      <ErrorBox message={state.error} />

      {unresolved.length > 0 && (
        <div className="my-4 rounded border-l-4 border-unverified bg-amber-50 px-4 py-3">
          Could not find these authors on Semantic Scholar: {unresolved.map((a) => a.name).join(", ")}.
          Conflicts with them cannot be checked. Enter their Semantic Scholar IDs instead.
        </div>
      )}

      {warnings.length > 0 && (
        <div className="my-4 rounded border-l-4 border-unverified bg-amber-50 px-4 py-3">
          <ul className="list-disc pl-5">
            {warnings.map((w, i) => <li key={i}>{show(w)}</li>)}
          </ul>
        </div>
      )}

      {data && instUsed.length > 0 && (
        <div className="my-4 rounded-lg border border-line bg-white px-4 py-3 text-sm">
          <p className="font-medium">Author institutions used for the check</p>
          <ul className="list-disc pl-5 text-muted">
            {instUsed.map((x, i) => <li key={i}>{show(x)}</li>)}
          </ul>
        </div>
      )}

      {data && (
        <div className="grid gap-4">
          {data.matches.map((m) => (
            <ResultCard key={m.scholar_id} match={m} onGraph={(id) => go("graph", id)} />
          ))}
        </div>
      )}
    </>
  );
}