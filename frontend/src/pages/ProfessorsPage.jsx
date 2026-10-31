import { useEffect } from "react";
import { api } from "../api.js";
import { useRequest } from "../components/useRequest.js";
import ErrorBox from "../components/ErrorBox.jsx";

const ghost = "mr-1.5 rounded-md bg-accent-soft px-3 py-1.5 text-sm text-accent";

export default function ProfessorsPage({ go }) {
  const [state, load] = useRequest(api.listIndexed);
  useEffect(() => { load(); }, []);
  const d = state.data;

  return (
    <>
      <h1 className="text-3xl">Indexed professors</h1>
      <p className="mb-6 mt-1.5 text-muted">Everyone currently in the reviewer pool.</p>

      <ErrorBox message={state.error} />
      {state.loading && <p className="text-muted">Loading...</p>}

      {d && d.professors.length === 0 && (
        <div className="rounded-lg border border-line bg-white p-5">
          No professors are indexed yet.{" "}
          <button className={ghost} onClick={() => go("index")}>Index your first professor</button>
        </div>
      )}

      {d && d.professors.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-line bg-white p-5">
          <p className="mb-3 text-muted">{d.total_professors} professors, {d.total_papers_indexed} papers</p>
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-line text-left">
                <th className="py-2 pr-3">Name</th><th className="py-2 pr-3">ID</th><th className="py-2 pr-3">Papers</th><th />
              </tr>
            </thead>
            <tbody>
              {d.professors.map((p) => (
                <tr key={p.scholar_id} className="border-b border-line">
                  <td className="py-2 pr-3">{p.professor_name}</td>
                  <td className="py-2 pr-3 text-muted">{p.scholar_id}</td>
                  <td className="py-2 pr-3">{p.paper_count}</td>
                  <td className="whitespace-nowrap py-2">
                    <button className={ghost} onClick={() => go("expertise", p.scholar_id)}>Expertise</button>
                    <button className={ghost} onClick={() => go("graph", p.scholar_id)}>Graph</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}