export interface MapFeature { id: string; name: string; description: string; source: "manifest" | "directory"; entrypoints: string[] }
export interface MapImport { source: string; target: string; line: number; specifier: string }
export interface MapCommit { sha: string; title: string; author: string | null; authored_at_iso: string | null; parents: string[]; parents_known: boolean; is_merge: boolean; files: { path: string; change: string; additions?: number; deletions?: number }[] }
export interface RepositoryMap { repo: string; head_sha: string | null; indexed_at_iso: string | null; total_files: number; files: { path: string; alive: boolean }[]; features: MapFeature[]; imports: MapImport[]; commits: MapCommit[]; total_commits: number; offset: number; has_more: boolean; coverage: Record<string, number>; warnings: string[] }
export interface FeatureImpact { feature: MapFeature; path: string[] }
export interface CommitImpact { direct: string[]; indirect: string[]; features: FeatureImpact[]; unindexed: string[] }
export interface MapNode { id: string; name: string; kind: "feature" | "file" | "commit"; affected?: boolean }
export interface MapEdge { source: string; target: string; kind: "imports" | "entry" | "changes" | "parent" | "shared"; label?: string }

export function featureFiles(data: RepositoryMap, feature: MapFeature): Set<string> {
  const adjacency = new Map<string, string[]>();
  for (const edge of data.imports) adjacency.set(edge.source, [...(adjacency.get(edge.source) ?? []), edge.target]);
  const result = new Set<string>();
  const todo = [...feature.entrypoints];
  while (todo.length) {
    const path = todo.pop()!;
    if (result.has(path)) continue;
    result.add(path);
    todo.push(...(adjacency.get(path) ?? []));
  }
  return result;
}

/** Reverse imports identify consumers. Each returned path runs entrypoint → dependency → changed file. */
export function commitImpact(data: RepositoryMap, commit: MapCommit): CommitImpact {
  const reverse = new Map<string, string[]>();
  for (const edge of data.imports) reverse.set(edge.target, [...(reverse.get(edge.target) ?? []), edge.source]);
  const direct = [...new Set(commit.files.map(file => file.path))];
  const paths = new Map(direct.map(path => [path, [path]]));
  const queue = [...direct];
  for (let i = 0; i < queue.length; i++) {
    for (const consumer of reverse.get(queue[i]) ?? []) {
      if (paths.has(consumer)) continue;
      paths.set(consumer, [consumer, ...paths.get(queue[i])!]);
      queue.push(consumer);
    }
  }
  const known = new Set(data.files.filter(file => file.alive).map(file => file.path));
  return {
    direct,
    indirect: queue.filter(path => !direct.includes(path)),
    unindexed: direct.filter(path => !known.has(path)),
    features: data.features.flatMap(feature => {
      const shortest = feature.entrypoints.map(path => paths.get(path)).filter((path): path is string[] => !!path).sort((a, b) => a.length - b.length)[0];
      return shortest ? [{ feature, path: shortest }] : [];
    }),
  };
}

export function mapGraph(data: RepositoryMap, featureId: string | null, commit: MapCommit | null, history: boolean): { nodes: MapNode[]; edges: MapEdge[]; omitted: number } {
  if (history) {
    const ids = new Set(data.commits.map(c => c.sha));
    return { nodes: data.commits.map(c => ({ id: c.sha, name: c.sha.slice(0, 7), kind: "commit", affected: c.sha === commit?.sha })),
      edges: data.commits.flatMap(c => c.parents.filter(p => ids.has(p)).map(p => ({ source: c.sha, target: p, kind: "parent" as const }))), omitted: 0 };
  }
  if (commit) {
    const impact = commitImpact(data, commit);
    const allPaths = [...new Set([...impact.features.flatMap(f => f.path), ...impact.direct])];
    const paths = allPaths.slice(0, 65);
    const ids = new Set(paths);
    const features = impact.features.filter(f => ids.has(f.path[0]));
    return {
      nodes: [{ id: commit.sha, name: commit.sha.slice(0, 7), kind: "commit", affected: true },
        ...features.map(f => ({ id: f.feature.id, name: f.feature.name, kind: "feature" as const, affected: true })),
        ...paths.map(path => ({ id: path, name: path.split("/").pop()!, kind: "file" as const, affected: impact.direct.includes(path) }))],
      edges: [...impact.direct.filter(p => ids.has(p)).map(p => ({ source: commit.sha, target: p, kind: "changes" as const })),
        ...features.map(f => ({ source: f.feature.id, target: f.path[0], kind: "entry" as const })),
        ...data.imports.filter(e => ids.has(e.source) && ids.has(e.target)).map(e => ({ source: e.source, target: e.target, kind: "imports" as const }))],
      omitted: allPaths.length - paths.length,
    };
  }
  const feature = data.features.find(f => f.id === featureId);
  if (feature) {
    const all = [...featureFiles(data, feature)];
    const paths = all.slice(0, 65);
    const ids = new Set(paths);
    return { nodes: [{ id: feature.id, name: feature.name, kind: "feature" }, ...paths.map(p => ({ id: p, name: p.split("/").pop()!, kind: "file" as const }))],
      edges: [...feature.entrypoints.filter(p => ids.has(p)).map(p => ({ source: feature.id, target: p, kind: "entry" as const })),
        ...data.imports.filter(e => ids.has(e.source) && ids.has(e.target)).map(e => ({ source: e.source, target: e.target, kind: "imports" as const }))], omitted: all.length - paths.length };
  }
  const sets = data.features.map(f => featureFiles(data, f));
  const edges: MapEdge[] = [];
  data.features.forEach((feature, i) => data.features.slice(i + 1).forEach((other, j) => {
    const shared = [...sets[i]].filter(p => sets[i + 1 + j].has(p));
    if (shared.length) edges.push({ source: feature.id, target: other.id, kind: "shared", label: `${shared.length} shared files` });
  }));
  return { nodes: data.features.map(f => ({ id: f.id, name: f.name, kind: "feature" })), edges, omitted: 0 };
}
