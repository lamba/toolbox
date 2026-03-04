#!/usr/bin/env python3
"""
AEP reverse lookup: find which schemas use which data types
(directly and indirectly via field groups).

Usage:
    python3 aep_datatype_usage.py \
      --schemas schemas.json \
      --datatypes datatypes.json \
      --fieldgroups fieldgroups.json \
      --out datatype_usage_report.json
    
    python3 aep_datatype_usage.py --schemas schemas.json --datatypes datatypes.json --fieldgroups fieldgroups.json --out datatype_usage_report.json
    
Optional filters:
    --datatype "Customer Profile"
    --datatype-id "https://ns.adobe.com/<tenant>/datatypes/abc123"
    --datatype-altid "_<tenant>.datatypes.abc123"
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Tuple, Set


# -----------------------------
# JSON loading helpers
# -----------------------------

def load_json_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_to_list(obj: Any) -> List[Dict[str, Any]]:
    """
    Normalize common export shapes to a list of dict resources.
    Supported:
      - [ {...}, {...} ]
      - { ...single resource... }
      - { "results": [ ... ] }
      - { "items": [ ... ] }
      - { "data": [ ... ] }
      - { "_embedded": { "results": [ ... ] } } (best effort)
    """
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]

    if isinstance(obj, dict):
        # Common wrappers
        for key in ("results", "items", "data"):
            if key in obj and isinstance(obj[key], list):
                return [x for x in obj[key] if isinstance(x, dict)]

        if "_embedded" in obj and isinstance(obj["_embedded"], dict):
            emb = obj["_embedded"]
            for key in ("results", "items", "data"):
                if key in emb and isinstance(emb[key], list):
                    return [x for x in emb[key] if isinstance(x, dict)]

        # Single resource object
        return [obj]

    return []


# -----------------------------
# Identity helpers
# -----------------------------

def resource_title(obj: Dict[str, Any]) -> str:
    return (
        obj.get("title")
        or obj.get("meta:title")
        or obj.get("name")
        or obj.get("displayName")
        or "(untitled)"
    )


def resource_id(obj: Dict[str, Any]) -> str:
    return obj.get("$id") or ""


def resource_altid(obj: Dict[str, Any]) -> str:
    return obj.get("meta:altId") or ""


def canonical_ids(obj: Dict[str, Any]) -> Set[str]:
    """
    Collect possible identifiers for matching.
    """
    ids = set()
    _id = resource_id(obj)
    alt = resource_altid(obj)
    if _id:
        ids.add(_id)
    if alt:
        ids.add(alt)

    # Sometimes references use xed ids in nested places (rare), keep simple here.
    return ids


# -----------------------------
# Recursive schema scanner
# -----------------------------

def collect_refs(node: Any, path: str = "$") -> List[Tuple[str, str]]:
    """
    Recursively collect all $ref values with their JSON-ish paths.
    Returns list of (path, ref_value).
    """
    found: List[Tuple[str, str]] = []

    if isinstance(node, dict):
        # Direct $ref
        if "$ref" in node and isinstance(node["$ref"], str):
            found.append((f"{path}.$ref", node["$ref"]))

        # Recurse all keys
        for k, v in node.items():
            child_path = f"{path}.{k}" if path else k
            found.extend(collect_refs(v, child_path))

    elif isinstance(node, list):
        for i, item in enumerate(node):
            child_path = f"{path}[{i}]"
            found.extend(collect_refs(item, child_path))

    return found


def find_datatype_refs_in_resource(
    resource_obj: Dict[str, Any],
    datatype_id_set: Set[str]
) -> List[Tuple[str, str]]:
    """
    Return refs in resource_obj that match any of the datatype identifiers.
    Match strategy:
      - exact match to datatype $id or meta:altId
      - suffix/contains fallback to handle some export variants
    """
    matches: List[Tuple[str, str]] = []
    refs = collect_refs(resource_obj)

    for path, ref in refs:
        if ref in datatype_id_set:
            matches.append((path, ref))
            continue

        # Fallbacks for variant formatting
        # e.g., if ref is URI and datatype id list has altId, or vice versa
        for dt_id in datatype_id_set:
            if not dt_id:
                continue
            if ref.endswith(dt_id) or dt_id.endswith(ref) or dt_id in ref or ref in dt_id:
                matches.append((path, ref))
                break

    return matches


# -----------------------------
# Field group extraction from schema
# -----------------------------

def extract_fieldgroup_refs_from_schema(schema_obj: Dict[str, Any]) -> Set[str]:
    """
    Extract field-group references attached to a schema.
    AEP schema objects typically include field groups in allOf[] as $ref entries.
    We return all refs and later intersect with known field group ids/alts.
    """
    refs = set(ref for _, ref in collect_refs(schema_obj))
    return refs


# -----------------------------
# Main analysis
# -----------------------------

def build_index(resources: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Map every canonical id (both $id and meta:altId) to the resource object.
    """
    idx: Dict[str, Dict[str, Any]] = {}
    for r in resources:
        for cid in canonical_ids(r):
            idx[cid] = r
    return idx


def main() -> int:
    parser = argparse.ArgumentParser(description="Find which AEP schemas use which data types")
    parser.add_argument("--schemas", required=True, help="Path to schemas JSON export")
    parser.add_argument("--datatypes", required=True, help="Path to data types JSON export")
    parser.add_argument("--fieldgroups", required=False, help="Path to field groups JSON export")
    parser.add_argument("--out", required=False, help="Output JSON report path")
    parser.add_argument("--datatype", required=False, help="Filter by data type title (contains match)")
    parser.add_argument("--datatype-id", required=False, help="Filter by exact datatype $id")
    parser.add_argument("--datatype-altid", required=False, help="Filter by exact datatype meta:altId")
    args = parser.parse_args()

    # Load
    schemas_raw = load_json_file(args.schemas)
    datatypes_raw = load_json_file(args.datatypes)
    fieldgroups_raw = load_json_file(args.fieldgroups) if args.fieldgroups else []

    schemas = normalize_to_list(schemas_raw)
    datatypes = normalize_to_list(datatypes_raw)
    fieldgroups = normalize_to_list(fieldgroups_raw)

    if not schemas:
        print("ERROR: No schemas found in input.", file=sys.stderr)
        return 1
    if not datatypes:
        print("ERROR: No data types found in input.", file=sys.stderr)
        return 1

    # Optional filter datatypes
    filtered_datatypes: List[Dict[str, Any]] = []
    for dt in datatypes:
        title = resource_title(dt)
        dt_id = resource_id(dt)
        dt_alt = resource_altid(dt)

        keep = True
        if args.datatype and args.datatype.lower() not in title.lower():
            keep = False
        if args.datatype_id and args.datatype_id != dt_id:
            keep = False
        if args.datatype_altid and args.datatype_altid != dt_alt:
            keep = False

        if keep:
            filtered_datatypes.append(dt)

    if not filtered_datatypes:
        print("ERROR: No datatypes matched the provided filter.", file=sys.stderr)
        return 1

    # Indexes
    fieldgroup_index = build_index(fieldgroups) if fieldgroups else {}

    # Canonical datatype lookup maps
    datatype_records = []
    datatype_ids_all: Set[str] = set()
    datatype_ids_to_record: Dict[str, Dict[str, Any]] = {}

    for dt in filtered_datatypes:
        dt_rec = {
            "title": resource_title(dt),
            "$id": resource_id(dt),
            "meta:altId": resource_altid(dt),
        }
        datatype_records.append(dt_rec)

        for cid in canonical_ids(dt):
            datatype_ids_all.add(cid)
            datatype_ids_to_record[cid] = dt_rec

    # Precompute datatype refs within each field group
    fieldgroup_datatype_hits: Dict[str, List[Dict[str, Any]]] = {}
    # keyed by fieldgroup canonical id (any known key we encounter)

    if fieldgroups:
        for fg in fieldgroups:
            fg_title = resource_title(fg)
            fg_id = resource_id(fg)
            fg_alt = resource_altid(fg)

            dt_hits = find_datatype_refs_in_resource(fg, datatype_ids_all)
            if not dt_hits:
                continue

            hit_rows = []
            for path, ref in dt_hits:
                # Try to resolve to the matched datatype record
                dt_rec = None
                if ref in datatype_ids_to_record:
                    dt_rec = datatype_ids_to_record[ref]
                else:
                    # fallback resolve by contains/suffix
                    for known_id, rec in datatype_ids_to_record.items():
                        if known_id and (known_id in ref or ref in known_id or ref.endswith(known_id) or known_id.endswith(ref)):
                            dt_rec = rec
                            break

                hit_rows.append({
                    "fieldgroup_title": fg_title,
                    "fieldgroup_$id": fg_id,
                    "fieldgroup_meta:altId": fg_alt,
                    "path": path,
                    "ref": ref,
                    "datatype": dt_rec,
                })

            # Store under all FG canonical ids so schema refs can resolve either way
            for fg_cid in canonical_ids(fg):
                fieldgroup_datatype_hits[fg_cid] = hit_rows

    # Analyze schemas
    report = {
        "summary": {
            "schema_count": len(schemas),
            "datatype_count_input": len(datatypes),
            "datatype_count_filtered": len(filtered_datatypes),
            "fieldgroup_count": len(fieldgroups),
        },
        "datatypes": [],
        "schemas_scanned": [],
    }

    # Result accumulator by datatype canonical $id (prefer $id else altId)
    datatype_usage_map: Dict[str, Dict[str, Any]] = {}
    for dt in filtered_datatypes:
        key = resource_id(dt) or resource_altid(dt) or resource_title(dt)
        datatype_usage_map[key] = {
            "datatype": {
                "title": resource_title(dt),
                "$id": resource_id(dt),
                "meta:altId": resource_altid(dt),
            },
            "schemas": []  # list of schema usage entries
        }

    for schema in schemas:
        schema_title = resource_title(schema)
        schema_id = resource_id(schema)
        schema_alt = resource_altid(schema)

        schema_entry_meta = {
            "title": schema_title,
            "$id": schema_id,
            "meta:altId": schema_alt,
        }
        report["schemas_scanned"].append(schema_entry_meta)

        # 1) Direct datatype refs in schema
        direct_hits = find_datatype_refs_in_resource(schema, datatype_ids_all)

        # Group direct hits by datatype key
        direct_by_datatype: Dict[str, List[Dict[str, str]]] = {}
        for path, ref in direct_hits:
            matched_dt = None
            if ref in datatype_ids_to_record:
                matched_dt = datatype_ids_to_record[ref]
            else:
                for known_id, rec in datatype_ids_to_record.items():
                    if known_id and (known_id in ref or ref in known_id or ref.endswith(known_id) or known_id.endswith(ref)):
                        matched_dt = rec
                        break

            if not matched_dt:
                continue

            dt_key = matched_dt.get("$id") or matched_dt.get("meta:altId") or matched_dt.get("title")
            direct_by_datatype.setdefault(dt_key, []).append({
                "path": path,
                "ref": ref
            })

        # 2) Indirect datatype refs via field groups attached to schema
        indirect_by_datatype: Dict[str, List[Dict[str, Any]]] = {}
        if fieldgroups:
            schema_refs = extract_fieldgroup_refs_from_schema(schema)

            # Resolve schema refs to known field groups by exact or fuzzy match
            matched_fieldgroups: List[Tuple[str, List[Dict[str, Any]]]] = []

            for sref in schema_refs:
                # exact
                if sref in fieldgroup_datatype_hits:
                    matched_fieldgroups.append((sref, fieldgroup_datatype_hits[sref]))
                    continue

                # fuzzy
                for fg_cid, fg_hits in fieldgroup_datatype_hits.items():
                    if fg_cid and (fg_cid in sref or sref in fg_cid or sref.endswith(fg_cid) or fg_cid.endswith(sref)):
                        matched_fieldgroups.append((fg_cid, fg_hits))
                        break

            # de-dup by fieldgroup canonical id
            seen_fg_cids = set()
            dedup_fieldgroups = []
            for fg_cid, fg_hits in matched_fieldgroups:
                if fg_cid in seen_fg_cids:
                    continue
                seen_fg_cids.add(fg_cid)
                dedup_fieldgroups.append((fg_cid, fg_hits))

            for _, fg_hits in dedup_fieldgroups:
                for hit in fg_hits:
                    dt_rec = hit.get("datatype")
                    if not dt_rec:
                        continue
                    dt_key = dt_rec.get("$id") or dt_rec.get("meta:altId") or dt_rec.get("title")
                    indirect_by_datatype.setdefault(dt_key, []).append({
                        "via_fieldgroup": {
                            "title": hit.get("fieldgroup_title"),
                            "$id": hit.get("fieldgroup_$id"),
                            "meta:altId": hit.get("fieldgroup_meta:altId"),
                        },
                        "fieldgroup_path": hit.get("path"),
                        "fieldgroup_ref": hit.get("ref"),
                    })

        # Merge into final datatype_usage_map
        all_dt_keys = set(direct_by_datatype.keys()) | set(indirect_by_datatype.keys())

        for dt_key in all_dt_keys:
            usage_entry = {
                "schema": schema_entry_meta,
                "direct_hits": direct_by_datatype.get(dt_key, []),
                "indirect_hits_via_fieldgroups": indirect_by_datatype.get(dt_key, []),
                "used_directly": dt_key in direct_by_datatype,
                "used_via_fieldgroup": dt_key in indirect_by_datatype,
            }

            # Avoid duplicate schema entries for same datatype
            existing = datatype_usage_map[dt_key]["schemas"]
            already = False
            for e in existing:
                if (e["schema"].get("$id") and e["schema"].get("$id") == schema_id) or \
                   (e["schema"].get("meta:altId") and e["schema"].get("meta:altId") == schema_alt) or \
                   (e["schema"].get("title") == schema_title):
                    already = True
                    break
            if not already:
                existing.append(usage_entry)

    # Build sorted datatypes output
    for dt_key, dt_block in datatype_usage_map.items():
        # sort schemas by title
        dt_block["schemas"].sort(key=lambda x: (x["schema"].get("title") or "").lower())
        dt_block["schema_count"] = len(dt_block["schemas"])
        dt_block["schemas_using_directly_count"] = sum(1 for s in dt_block["schemas"] if s["used_directly"])
        dt_block["schemas_using_via_fieldgroup_count"] = sum(1 for s in dt_block["schemas"] if s["used_via_fieldgroup"])
        report["datatypes"].append(dt_block)

    report["datatypes"].sort(key=lambda d: (d["datatype"].get("title") or "").lower())

    # Output JSON
    output_text = json.dumps(report, indent=2, ensure_ascii=False)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output_text)
        print(f"Wrote report to {args.out}")

    # Also print a concise console summary
    print("\n=== Data Type Usage Summary ===")
    for dt in report["datatypes"]:
        d = dt["datatype"]
        print(
            f"- {d.get('title')} "
            f"(schemas={dt['schema_count']}, "
            f"direct={dt['schemas_using_directly_count']}, "
            f"via_fieldgroup={dt['schemas_using_via_fieldgroup_count']})"
        )

    # If no --out, print full JSON to stdout
    if not args.out:
        print("\n" + output_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())