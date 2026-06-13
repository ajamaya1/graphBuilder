#!/usr/bin/env python3
"""
generate-graph-props.py
Extracts the FULL scalar property set for each resource entity from Microsoft's
Graph OpenAPI spec (components/schemas), resolving allOf inheritance, and writes
graph-props.js:  window.GRAPH_PROPS = { managedDevices: ["a","b",...], ... }

So $select / $filter / $orderby can offer every column a JSON response can return,
not a hand-curated subset. Run by the same weekly GitHub Action as the path index.

Only scalar + simple-array properties are listed (string, boolean, number, date,
enum, array-of-string) — nested objects and navigation properties are skipped,
since those aren't directly selectable as columns.
"""
import json
import re
import sys
import urllib.request

SPEC = "https://raw.githubusercontent.com/microsoftgraph/msgraph-metadata/master/openapi/{ver}/openapi.yaml"

# resource id -> the microsoft.graph schema entity that its rows are
ENTITY = {
    "managedDevices": "managedDevice",
    "cloudPCs": "cloudPC",
    "autopilot": "windowsAutopilotDeviceIdentity",
    "deviceConfigurations": "deviceConfiguration",
    "configurationPolicies": "deviceManagementConfigurationPolicy",
    "compliancePolicies": "deviceCompliancePolicy",
    "deviceHealthScripts": "deviceHealthScript",
    "mobileApps": "mobileApp",
    "users": "user",
    "groups": "group",
    "devices": "device",
    "signIns": "signIn",
    "me": "user",
    "directoryRoles": "directoryRole",
    "roleDefinitions": "unifiedRoleDefinition",
    "organization": "organization",
    "domains": "domain",
    "subscribedSkus": "subscribedSku",
    "applications": "application",
    "servicePrincipals": "servicePrincipal",
    "conditionalAccessPolicies": "conditionalAccessPolicy",
    "namedLocations": "namedLocation",
    "riskyUsers": "riskyUser",
    "riskDetections": "riskDetection",
    "detectedApps": "detectedApp",
    "deviceCategories": "deviceCategory",
    "enrollmentConfigurations": "deviceEnrollmentConfiguration",
    "assignmentFilters": "deviceAndAppManagementAssignmentFilter",
    "securityAlerts": "security.alert",
    "securityIncidents": "security.incident",
    "secureScores": "secureScore",
    "directoryAudits": "directoryAudit",
}

SCALAR_TYPES = {"string", "boolean", "integer", "number"}


def fetch(ver: str) -> str:
    url = SPEC.format(ver=ver)
    print(f"  downloading {ver} spec …", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "graphbuilder-props-updater"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_schemas(yaml_text: str) -> dict:
    """
    Returns { 'microsoft.graph.user': {'props': set(), 'bases': [refs]} }.
    Walks components/schemas line by line. A property name sits at 12-space indent
    under a 'properties:' line; its attribute lines sit at 14-space. We read each
    property's attribute block to decide if it's a selectable scalar/simple-array.
    allOf $refs are captured so inherited props merge in afterward.
    """
    schemas = {}
    lines = yaml_text.splitlines()

    start = None
    for i, l in enumerate(lines):
        if l.rstrip() == "  schemas:":
            start = i + 1
            break
    if start is None:
        return schemas

    schema_re = re.compile(r"^    (microsoft\.graph\.[\w.]+):\s*$")
    ref_re = re.compile(r"^\s*- \$ref: '#/components/schemas/(microsoft\.graph\.[\w.]+)'")
    prop_key_re = re.compile(r"^            (\w[\w]*):\s*$")   # exactly 12-space indent
    attr_type_re = re.compile(r"^              type:\s*(\w+)")  # 14-space
    attr_format_re = re.compile(r"^              format:\s*date-time")
    attr_ref_re = re.compile(r"^              \$ref:")
    attr_anyof_re = re.compile(r"^              (anyOf|allOf|oneOf):")
    items_type_re = re.compile(r"^                type:\s*(string|integer|number|boolean)")  # 16-space, array item

    n = len(lines)
    cur = None
    in_props = False
    i = start
    while i < n:
        l = lines[i]
        # end of components/schemas: a 0- or 2-space top-level key
        if l and not l.startswith("    ") and l.rstrip().endswith(":"):
            break
        m = schema_re.match(l)
        if m:
            cur = m.group(1)
            schemas[cur] = {"props": set(), "bases": []}
            in_props = False
            i += 1
            continue
        if cur is None:
            i += 1
            continue
        if not in_props:
            rm = ref_re.match(l)
            if rm:
                schemas[cur]["bases"].append(rm.group(1))
        if l.rstrip() == "          properties:":   # exactly 10-space properties:
            in_props = True
            i += 1
            continue
        if in_props:
            pk = prop_key_re.match(l)
            if pk:
                name = pk.group(1)
                # scan this property's 14-space (+) attribute lines
                is_scalar = False
                is_array = False
                array_scalar = False
                disqualified = False
                j = i + 1
                while j < n:
                    a = lines[j]
                    if prop_key_re.match(a) or schema_re.match(a):
                        break
                    if a.rstrip() == "          properties:" or a.startswith("            ") is False:
                        # left this property's attribute block (dedent past 12-space)
                        if a.strip() and not a.startswith("              ") and not a.startswith("                "):
                            break
                    tm = attr_type_re.match(a)
                    if tm:
                        if tm.group(1) == "array":
                            is_array = True
                        elif tm.group(1) in SCALAR_TYPES:
                            is_scalar = True
                    if attr_format_re.match(a):
                        is_scalar = True
                    if attr_ref_re.match(a) or attr_anyof_re.match(a):
                        disqualified = True
                    if is_array and items_type_re.match(a):
                        array_scalar = True
                    j += 1
                if (is_scalar and not is_array) or (is_array and array_scalar):
                    if not (disqualified and not is_scalar and not array_scalar):
                        schemas[cur]["props"].add(name)
                i = j
                continue
        i += 1
    return schemas


def resolve(entity: str, schemas: dict, seen=None) -> set:
    """Merge an entity's own props with all inherited (allOf) base props."""
    if seen is None:
        seen = set()
    key = f"microsoft.graph.{entity}"
    if key not in schemas or key in seen:
        return set()
    seen.add(key)
    props = set(schemas[key]["props"])
    for base in schemas[key]["bases"]:
        bare = base.replace("microsoft.graph.", "")
        props |= resolve(bare, schemas, seen)
    return props


def main() -> int:
    # beta has the widest property coverage; use it as the source of truth
    yaml_text = fetch("beta")
    schemas = parse_schemas(yaml_text)
    print(f"  parsed {len(schemas)} schemas", flush=True)
    if len(schemas) < 500:
        print(f"  ERROR: only {len(schemas)} schemas — aborting.", file=sys.stderr)
        return 1

    out = {}
    for rid, entity in ENTITY.items():
        props = resolve(entity, schemas)
        # always surface id first if present, then alphabetical
        ordered = (["id"] if "id" in props else []) + sorted(p for p in props if p != "id")
        if ordered:
            out[rid] = ordered

    js = "window.GRAPH_PROPS=" + json.dumps(out, separators=(",", ":"))
    with open("graph-props.js", "w", encoding="utf-8") as f:
        f.write(js)
    total = sum(len(v) for v in out.values())
    print(f"wrote graph-props.js — {len(out)} resources, {total} properties total ({len(js)/1024:.0f} KB)")
    for rid in ("users", "groups", "managedDevices", "devices"):
        if rid in out:
            print(f"  {rid}: {len(out[rid])} properties")
    return 0


if __name__ == "__main__":
    sys.exit(main())
