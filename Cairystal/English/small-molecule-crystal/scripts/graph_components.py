"""Reduce permutations of interchangeable disconnected fragments in an exact match."""
from collections import defaultdict
import json
import math


def components(adj):
    remaining = set(adj)
    groups = []
    while remaining:
        pending = [min(remaining)]
        part = set(pending)
        while pending:
            unseen = set(adj[pending.pop()]) - part
            part.update(unseen)
            pending.extend(unseen)
        remaining -= part
        groups.append(sorted(part))
    return groups


def small_fragment_key(part, atoms, adj):
    """An exact labelled tree or simple-ring representation. Other shapes use full search."""
    if len(part) > 32:
        return None
    color = {k: json.dumps({key:v for key,v in atoms[k].items() if key!='id'},
                           sort_keys=True, separators=(',',':')) for k in part}
    if sum(len(adj[k]) for k in part) == 2*(len(part)-1):
        def branch(k, parent):
            return color[k], tuple(sorted((order,branch(j,k)) for j,order in adj[k].items() if j!=parent))
        return 'tree', min(branch(k,None) for k in part)
    if not all(len(adj[k]) == 2 for k in part):
        return None
    walks=[]
    for start in part:
        for second in adj[start]:
            k,j=start,second
            walk=[]
            while True:
                walk.append((color[k],adj[k][j]))
                if j==start:
                    break
                k,j=j,next(v for v in adj[j] if v!=k)
            walks.append(tuple(walk))
    return 'ring', min(walks)


def restrict_copies(atoms, adj, current, neighbors, domains, interchangeable, parts):
    def coarse(part, sites, edges):
        return tuple(sorted((len(edges[k]),'*' if sites[k]['element'] in interchangeable else sites[k]['element'])
                            for k in part))
    targets=defaultdict(list)
    for part in components(neighbors):
        targets[coarse(part,current,neighbors)].append(part)
    families=defaultdict(list)
    for part in parts:
        topology=coarse(part,atoms,adj)
        if len(targets[topology])<2:
            continue
        exact=small_fragment_key(part,atoms,adj)
        if exact is not None:
            families[(topology,exact)].append(part)
    reduced=[]
    for (topology,_), copies in families.items():
        placements=targets[topology]
        # Every exact match must use precisely these target components, once each.
        # A competing solvent with the same coarse topology requires full enumeration.
        if len(copies)<2 or len(copies)!=len(placements):
            continue
        for copy,placement in zip(copies,placements):
            allowed=set(placement)
            for k in copy:
                domains[k]=[label for label in domains[k] if label in allowed]
        reduced.append(dict(copies=len(copies), atoms_per_copy=len(copies[0]),
                            label_permutations=math.factorial(len(copies))))
    return reduced
