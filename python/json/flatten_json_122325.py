#!/usr/bin/env python3
import json
import sys

def flatten_schema(node, parent_key=""):
    """
    Flatten a JSON Schema/XDM schema into dot-notation field paths.

    - Treats "properties" as *transparent* (not part of the path)
    - Records each field name once it appears under "properties"
    - Recurses into nested objects
    """
    paths = []

    if isinstance(node, dict):
        # JSON Schema / XDM style: children live under "properties"
        props = node.get("properties")
        if isinstance(props, dict):
            for field_name, field_schema in props.items():
                full_path = f"{parent_key}.{field_name}" if parent_key else field_name
                # record this field
                paths.append(full_path)
                # and recurse into its children (if any)
                paths.extend(flatten_schema(field_schema, full_path))

    elif isinstance(node, list):
        # Some schemas might have arrays of subschemas
        for item in node:
            paths.extend(flatten_schema(item, parent_key))

    return paths


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <schema-json-file>", file=sys.stderr)
        sys.exit(1)

    schema_path = sys.argv[1]

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    # For AEP union schemas, the root is the schema object itself
    flattened_paths = flatten_schema(schema)

    for p in sorted(set(flattened_paths)):
        print(p)


if __name__ == "__main__":
    main()
