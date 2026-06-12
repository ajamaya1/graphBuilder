#!/usr/bin/env python3
"""
generate-graph-paths.py
Rebuilds graph-paths.js from Microsoft's official Graph OpenAPI specs
(github.com/microsoftgraph/msgraph-metadata). Run by GitHub Actions on a
schedule so new/deprecated Graph endpoints flow into the app automatically.

No dependencies — stdlib only. Line-scans the (very large) YAML rather than
fully parsing it, which is fast and matches the spec's stable formatting:

paths:
  /deviceManagement/managedDevices:
    get:
    post:
  /deviceManagement/managedDevices/{managedDevice-id}:
    ...

Output format (must match what index.html expects):
window.GRAPH_PATHS={v1:"/path~GO\n/path2~GAD...",beta:"..."}
Method letters: G=GET, O=POST, A=PATCH, U=PUT, D=DELETE
"""
import json
import re
import sys
import urllib.request

SPECS = {
    "v1": "https://raw.githubusercontent.com/microsoftgraph/msgraph-metadata/master/openapi/v1.0/openapi.yaml",
    "beta": "https://raw.githubusercontent.com/microsoftgraph/msgraph-metadata/master/openapi/beta/openapi.yaml",
}
METHOD_LETTER = {"get": "G", "post": "O", "patch": "A", "put": "U", "delete": "D"}
# stable letter order so diffs stay minimal between runs
LETTER_ORDER = "GOAUD"


def fetch(url: str) -> str:
    print(f"  downloading {url} …", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "graphbuilder-paths-updater"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = r.read().decode("utf-8", errors="replace")
    print(f"  {len(data)/1e6:.1f} MB", flush=True)
    return data


def extract_paths(yaml_text: str) -> dict:
    """Line-scan the OpenAPI YAML for path keys and their HTTP methods."""
    paths = {}
    current = None
    in_paths = False
    path_re = re.compile(r"^  '?(/[^\s:']*)'?:\s*$")   # 2-space indent: a path key (may be 'quoted')
    method_re = re.compile(r"^    (get|post|patch|put|delete):\s*$")  # 4-space indent

    for line in yaml_text.splitlines():
        if not in_paths:
            if line.rstrip() == "paths:":
                in_paths = True
            continue
        # a new top-level key (0-indent, e.g. components:) ends the paths block
        if line and not line.startswith(" ") and line.rstrip().endswith(":"):
            break
        m = path_re.match(line)
        if m:
            current = m.group(1)
            paths.setdefault(current, set())
            continue
        if current:
            m = method_re.match(line)
            if m:
                paths[current].add(METHOD_LETTER[m.group(1)])
    return paths


def encode(paths: dict) -> str:
    lines = []
    for p in sorted(paths):
        letters = "".join(l for l in LETTER_ORDER if l in paths[p])
        if letters:
            lines.append(f"{p}~{letters}")
    return "\n".join(lines)


def main() -> int:
    out = {}
    for key, url in SPECS.items():
        print(f"[{key}]", flush=True)
        yaml_text = fetch(url)
        paths = extract_paths(yaml_text)
        if len(paths) < 1000:
            # sanity guard: Microsoft's spec always has thousands of paths.
            # A tiny result means the download or format changed — do NOT
            # overwrite a good file with a broken one.
            print(f"  ERROR: only {len(paths)} paths extracted — aborting without writing.", file=sys.stderr)
            return 1
        out[key] = encode(paths)
        print(f"  {len(paths)} paths", flush=True)

    js = "window.GRAPH_PATHS={v1:" + json.dumps(out["v1"]) + ",beta:" + json.dumps(out["beta"]) + "}"
    with open("graph-paths.js", "w", encoding="utf-8") as f:
        f.write(js)
    print(f"wrote graph-paths.js ({len(js)/1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
