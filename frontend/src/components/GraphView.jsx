// Radial layout, no graph library: reviewer in the centre, papers on a ring,
// co-authors on an outer ring at the average angle of their papers.
const FILL = { reviewer: "#14213d", paper: "#0f5c73", coauthor: "#a86a0a" };
const RADIUS = { reviewer: 14, paper: 5, coauthor: 4 };

export default function GraphView({ nodes, edges }) {
  const reviewer = nodes.find((n) => n.type === "reviewer");
  const papers = nodes.filter((n) => n.type === "paper").sort((a, b) => (a.year ?? 0) - (b.year ?? 0));
  const coauthors = nodes.filter((n) => n.type === "coauthor");

  const r1 = Math.max(160, papers.length * 7);
  const r2 = r1 + 130;
  const size = (r2 + 40) * 2;
  const c = size / 2;

  const pos = { [reviewer.id]: [c, c] };
  const angle = {};
  papers.forEach((p, i) => {
    const a = (2 * Math.PI * i) / papers.length;
    angle[p.id] = a;
    pos[p.id] = [c + r1 * Math.cos(a), c + r1 * Math.sin(a)];
  });

  const paperAngles = {};
  edges.forEach(({ source, target }) => {
    if (angle[target] !== undefined && source !== reviewer.id) (paperAngles[source] ||= []).push(angle[target]);
  });
  coauthors.forEach((n, i) => {
    const list = paperAngles[n.id] || [0];
    const x = list.reduce((s, a) => s + Math.cos(a), 0);
    const y = list.reduce((s, a) => s + Math.sin(a), 0);
    const a = Math.atan2(y, x) + (i % 7) * 0.01; // tiny offset so overlapping nodes separate
    const rr = r2 + (i % 3) * 18;
    pos[n.id] = [c + rr * Math.cos(a), c + rr * Math.sin(a)];
  });

  return (
    <svg width={size} height={size} role="img" aria-label="Collaboration graph">
      {edges.map((e, i) =>
        pos[e.source] && pos[e.target] ? (
          <line key={i} x1={pos[e.source][0]} y1={pos[e.source][1]} x2={pos[e.target][0]} y2={pos[e.target][1]}
            stroke="#c5ccd6" strokeWidth="0.8" />
        ) : null
      )}
      {nodes.map((n) =>
        pos[n.id] ? (
          <circle key={n.id} cx={pos[n.id][0]} cy={pos[n.id][1]} r={RADIUS[n.type]} fill={FILL[n.type]}>
            <title>{n.label}{n.year ? ` (${n.year})` : ""}</title>
          </circle>
        ) : null
      )}
      <text x={c} y={c + 30} textAnchor="middle" fontSize="13" fontWeight="600" fill="#14213d">{reviewer.label}</text>
    </svg>
  );
}