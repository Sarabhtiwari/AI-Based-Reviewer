import { useState } from "react";
import MatchPage from "./pages/MatchPage.jsx";
import IndexPage from "./pages/IndexPage.jsx";
import ProfessorsPage from "./pages/ProfessorsPage.jsx";
import ExpertisePage from "./pages/ExpertisePage.jsx";
import GraphPage from "./pages/GraphPage.jsx";

const PAGES = [
  ["match", "Match reviewers"],
  ["index", "Index professors"],
  ["professors", "Indexed professors"],
  ["expertise", "Expertise"],
  ["graph", "Collaboration graph"],
];

export default function App() {
  const [nav, setNav] = useState({ page: "match", id: "" });
  const go = (page, id = "") => setNav({ page, id });

  return (
    <div className="min-h-screen md:grid md:grid-cols-[230px_1fr]">
      <nav
        aria-label="Main"
        className="flex gap-1 overflow-x-auto bg-ink p-3 text-slate-200 md:sticky md:top-0 md:block md:h-screen md:px-4 md:py-7"
      >
        <div className="mb-7 hidden px-2 font-serif text-2xl font-semibold text-white md:block">
          Reviewer Desk
        </div>
        {PAGES.map(([key, label]) => (
          <button
            key={key}
            aria-current={nav.page === key ? "page" : undefined}
            onClick={() => go(key)}
            className="w-full whitespace-nowrap rounded-md px-3 py-2.5 text-left hover:bg-white/10 aria-[current=page]:bg-white aria-[current=page]:font-semibold aria-[current=page]:text-ink md:block"
          >
            {label}
          </button>
        ))}
      </nav>

      <main className="max-w-5xl p-5 pb-16 md:px-11 md:py-9">
        {nav.page === "match" && <MatchPage go={go} />}
        {nav.page === "index" && <IndexPage go={go} />}
        {nav.page === "professors" && <ProfessorsPage go={go} />}
        {nav.page === "expertise" && <ExpertisePage key={nav.id} initialId={nav.id} />}
        {nav.page === "graph" && <GraphPage key={nav.id} initialId={nav.id} />}
      </main>
    </div>
  );
}