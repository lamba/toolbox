#!/usr/bin/env python3
"""
AEP 1-hop graph lookup.

Given an ID for a:
  - data type
  - field group (mixin)
  - schema
  - dataset
return all 1-hop connections in ALL directions.

Usage:
  python aep_1hop.py \
    --schemas schemas.json \
    --fieldgroups fieldgroups.json \
    --datatypes datatypes.json \
    --datasets datasets.json \
    --id "<some $id or meta:altId>" \
    --out neighbors.json

python3 aep-1hop.py --schemas schemas.json --fieldgroups fieldgroups.json --datatypes datatypes.json --datasets datasets.json --id "<some $id or meta:altId>" --out neighbors.json

Notes:
- Best results when schema/fg/dt exports preserve $ref (Accept: application/vnd.adobe.xed+json).
- Handles common wrapper shapes: list, {"results":[]}, {"items":[]}, {"data":[]}.
"""

import argparse
import json
import sys
from typing import Any, Dict, List, Tuple, Set, Optional


# -----------------------------
# JSON loading helpers
# -----------------------------

def load_json(path: Optional[str]) -> Any:
    if not path:
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def normalize_to_list(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for k in ("results", "items", "data"):
            if k in obj and isinstance(obj[k], list):
                return [x for x in obj[k] if isinstance(x, dict)]
        if "_embedded" in obj and isinstance(obj["_embedded"], dict):
            emb = obj["_embedded"]
            for k in ("results", "items", "data"):
                if k in emb and isinstance(emb[k], list):
                    return [x for x in emb[k] if isinstance(x, dict)]
        return [obj]
    return []

# -----------------------------
# Resource identity helpers
# -----------------------------

def title_of(o: Dict[str, Any]) -> str:
    return o.get("title") or o.get("meta:title") or o.get("name") or o.get("displayName") or "(untitled)"

def id_of(o: Dict[str, Any]) -> str:
    return o.get("$id") or ""

def altid_of(o: Dict[str, Any]) -> str:
    return o.get("meta:altId") or ""

def canonical_ids(o: Dict[str, Any]) -> Set[str]:
    s = set()
    if id_of(o): s.add(id_of(o))
    if altid_of(o): s.add(altid_of(o))
    return s

def make_node(kind: str, o: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": kind,
        "title": title_of(o),
        "$id": id_of(o),
        "meta:altId": altid_of(o),
    }

# -----------------------------
# Ref scanning
# -----------------------------

def collect_refs(node: Any, path: str = "$") -> List[Tuple[str, str]]:
    found: List[Tuple[str, str]] = []
    if isinstance(node, dict):
        if "$ref" in node and isinstance(node["$ref"], str):
            found.append((f"{path}.$ref", node["$ref"]))
        for k, v in node.items():
            found.extend(collect_refs(v, f"{path}.{k}"))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            found.extend(collect_refs(item, f"{path}[{i}]"))
    return found

# -----------------------------
# Dataset -> schema extraction
# -----------------------------

def dataset_schema_refs(ds: Dict[str, Any]) -> Set[str]:
    """
    Try common locations for dataset->schema reference.
    Catalog datasets can vary by export. We try several patterns.
    """
    refs: Set[str] = set()

    # Common patterns
    candidates = [
        ("schemaRef",),
        ("schema", "id"),
        ("schema", "$id"),
        ("schema", "ref"),
        ("schema",),
        ("xdm", "schema"),
        ("xdm", "schemaRef"),
    ]

    def get_path(o: Any, path: Tuple[str, ...]) -> Any:
        cur = o
        for p in path:
            if not isinstance(cur, dict) or p not in cur:
                return None
            cur = cur[p]
        return cur

    for p in candidates:
        v = get_path(ds, p)
        if isinstance(v, str) and v:
            refs.add(v)

    # Some exports include schema in "tags" or elsewhere, but avoid guessing too hard.
    return refs

# -----------------------------
# Graph build
# -----------------------------

def build_index(resources: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    idx: Dict[str, Dict[str, Any]] = {}
    for r in resources:
        for cid in canonical_ids(r):
            idx[cid] = r
    return idx

def add_edge(adj: Dict[str, Dict[str, Any]],
             a_id: str, a_node: Dict[str, Any],
             b_id: str, b_node: Dict[str, Any],
             reason: str, path: Optional[str] = None):
    """
    Undirected adjacency: store neighbor and why.
    """
    if not a_id or not b_id or a_id == b_id:
        return

    adj.setdefault(a_id, {"node": a_node, "neighbors": []})
    adj.setdefault(b_id, {"node": b_node, "neighbors": []})

    adj[a_id]["neighbors"].append({
        "id": b_id,
        "node": b_node,
        "reason": reason,
        **({"path": path} if path else {})
    })
    adj[b_id]["neighbors"].append({
        "id": a_id,
        "node": a_node,
        "reason": reason,
        **({"path": path} if path else {})
    })

def dedup_neighbors(neighbors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for n in neighbors:
        key = (n["id"], n.get("reason"), n.get("path"))
        if key in seen:
            continue
        seen.add(key)
        out.append(n)
    return out

# -----------------------------
# Main
# -----------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schemas", required=True)
    ap.add_argument("--fieldgroups", required=True)
    ap.add_argument("--datatypes", required=True)
    ap.add_argument("--datasets", required=False)
    ap.add_argument("--id", required=True, help="Any $id or meta:altId for schema/fg/dt/dataset")
    ap.add_argument("--out", required=False)
    args = ap.parse_args()

    schemas = normalize_to_list(load_json(args.schemas))
    fieldgroups = normalize_to_list(load_json(args.fieldgroups))
    datatypes = normalize_to_list(load_json(args.datatypes))
    datasets = normalize_to_list(load_json(args.datasets)) if args.datasets else []

    schema_idx = build_index(schemas)
    fg_idx = build_index(fieldgroups)
    dt_idx = build_index(datatypes)
    ds_idx = build_index(datasets)  # datasets likely don't have meta:altId; still fine

    # Build a set of all canonical ids to match refs against
    schema_ids = set(schema_idx.keys())
    fg_ids = set(fg_idx.keys())
    dt_ids = set(dt_idx.keys())
    ds_ids = set(ds_idx.keys())

    # Prefer matching $id/altId style by containment as fallback
    def match_known(ref: str, known_ids: Set[str]) -> Optional[str]:
        if ref in known_ids:
            return ref
        for kid in known_ids:
            if kid and (kid in ref or ref in kid or ref.endswith(kid) or kid.endswith(ref)):
                return kid
        return None

    adj: Dict[str, Dict[str, Any]] = {}

    # ---- 1) Schema <-> Fieldgroup edges via schema allOf $ref
    for s in schemas:
        s_node = make_node("schema", s)
        s_primary = id_of(s) or altid_of(s)  # pick a stable key
        if not s_primary:
            continue

        for path, ref in collect_refs(s):
            fg_match = match_known(ref, fg_ids)
            if fg_match:
                fg_obj = fg_idx[fg_match]
                fg_node = make_node("fieldgroup", fg_obj)
                add_edge(adj, s_primary, s_node,
                         fg_match, fg_node,
                         reason="schema_includes_fieldgroup", path=path)

    # ---- 2) Schema/Fieldgroup <-> Datatype edges via any $ref
    for s in schemas:
        s_node = make_node("schema", s)
        s_primary = id_of(s) or altid_of(s)
        if not s_primary:
            continue
        for path, ref in collect_refs(s):
            dt_match = match_known(ref, dt_ids)
            if dt_match:
                dt_obj = dt_idx[dt_match]
                dt_node = make_node("datatype", dt_obj)
                add_edge(adj, s_primary, s_node,
                         dt_match, dt_node,
                         reason="schema_refs_datatype", path=path)

    for fg in fieldgroups:
        fg_node = make_node("fieldgroup", fg)
        fg_primary = id_of(fg) or altid_of(fg)
        if not fg_primary:
            continue
        for path, ref in collect_refs(fg):
            dt_match = match_known(ref, dt_ids)
            if dt_match:
                dt_obj = dt_idx[dt_match]
                dt_node = make_node("datatype", dt_obj)
                add_edge(adj, fg_primary, fg_node,
                         dt_match, dt_node,
                         reason="fieldgroup_refs_datatype", path=path)

    # ---- 3) Dataset <-> Schema edges via dataset schemaRef-ish fields
    for ds in datasets:
        ds_node = {
            "kind": "dataset",
            "title": title_of(ds),
            "$id": id_of(ds),  # might be empty depending on export
            "meta:altId": altid_of(ds),
        }
        ds_primary = id_of(ds) or altid_of(ds) or ds.get("id") or ds.get("_id") or ds.get("name")
        if not ds_primary:
            # As last resort, skip
            continue

        for sref in dataset_schema_refs(ds):
            sm = match_known(sref, schema_ids)
            if sm:
                s_obj = schema_idx[sm]
                s_node = make_node("schema", s_obj)
                add_edge(adj, ds_primary, ds_node,
                         sm, s_node,
                         reason="dataset_implements_schema", path="dataset.schemaRef")

    # ---- Normalize / dedupe adjacency lists
    for k in list(adj.keys()):
        adj[k]["neighbors"] = dedup_neighbors(adj[k]["neighbors"])

    query_id = args.id

    # Try to resolve query_id if it's not an exact key
    resolved = None
    if query_id in adj:
        resolved = query_id
    else:
        # try to fuzzy match against known adjacency keys
        for kid in adj.keys():
            if kid and (kid == query_id or kid in query_id or query_id in kid or kid.endswith(query_id) or query_id.endswith(kid)):
                resolved = kid
                break

    if not resolved:
        print(f"ERROR: Could not find node for id '{query_id}'.", file=sys.stderr)
        print("Tip: ensure you're passing a $id or meta:altId that exists in your input files.", file=sys.stderr)
        return 1

    result = {
        "query": {
            "input_id": query_id,
            "resolved_id": resolved,
            "node": adj[resolved]["node"],
        },
        "neighbors_1hop": adj[resolved]["neighbors"],
        "neighbor_count": len(adj[resolved]["neighbors"]),
    }

    out_text = json.dumps(result, indent=2, ensure_ascii=False)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out_text)
        print(f"Wrote 1-hop neighbors to {args.out}")
    else:
        print(out_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())