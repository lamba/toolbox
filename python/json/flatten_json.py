#!/usr/bin/env python3
import json
import os
import sys

def flatten_schema(node, parent_key=""):
    """
    Flatten a JSON Schema/XDM schema into dot-notation field paths.

    - Treats "properties" as transparent (not part of the path)
    - Records each field name once it appears under "properties"
    - Recurses into nested objects, arrays ("items"), and composed schemas
    """
    paths = set()

    if isinstance(node, dict):
        # 1) Normal object properties
        props = node.get("properties")
        if isinstance(props, dict):
            for field_name, field_schema in props.items():
                full_path = f"{parent_key}.{field_name}" if parent_key else field_name
                # record this field
                paths.add(full_path)
                # recurse into its children (if any)
                paths |= flatten_schema(field_schema, full_path)

        # 2) Arrays: follow "items" but keep the same path (no [] in the name)
        items = node.get("items")
        if items is not None:
            paths |= flatten_schema(items, parent_key)

        # 3) Composed schemas: allOf / anyOf / oneOf
        for key in ("allOf", "anyOf", "oneOf"):
            subschemas = node.get(key)
            if isinstance(subschemas, list):
                for sub in subschemas:
                    paths |= flatten_schema(sub, parent_key)

        # 4) Map-like structures: additionalProperties with its own schema
        addl = node.get("additionalProperties")
        if isinstance(addl, dict):
            paths |= flatten_schema(addl, parent_key)

    elif isinstance(node, list):
        # Arrays of subschemas (rare but possible)
        for item in node:
            paths |= flatten_schema(item, parent_key)

    return paths


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <schema-json-file>", file=sys.stderr)
        sys.exit(1)

    schema_path = sys.argv[1]

    # Derive output path: same folder & base name, .txt extension
    base, _ = os.path.splitext(schema_path)
    output_path = base + ".txt"

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    flattened_paths = sorted(flatten_schema(schema))

    with open(output_path, "w", encoding="utf-8") as out_f:
        out_f.write("\n".join(flattened_paths))

    print(f"Wrote {len(flattened_paths)} paths to {output_path}")


if __name__ == "__main__":
    main()
