"""Conservative, configuration-reference edges; no inferred network routes."""
import re

def build_edges(configuration, nodes):
    addresses = {n["id"] for n in nodes}
    edges, limits = {}, []
    def refs(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "references" and isinstance(child, list):
                    yield from (v for v in child if isinstance(v, str))
                elif key != "constant_value":
                    yield from refs(child)
        elif isinstance(value, list):
            for child in value:
                yield from refs(child)
    def walk(module, prefix=""):
        if not isinstance(module, dict):
            return
        resources = module.get("resources", [])
        if not isinstance(resources, list):
            return
        for resource in resources:
            if not isinstance(resource, dict) or not isinstance(resource.get("address"), str):
                continue
            source = prefix + resource["address"]
            # Indexed module/resource expansion is deliberately not guessed.
            if source not in addresses:
                continue
            for ref in refs(resource.get("expressions", {})):
                full = prefix + ref
                candidates = [a for a in addresses if full == a or full.startswith(a + ".")]
                if not candidates:
                    continue
                target = max(candidates, key=len)
                if target == source:
                    continue
                key = (target, source)
                edges[key] = {"id": target + "->" + source, "source": target, "target": source, "kind": "reference", "evidence": "configuration.expressions.references", "label": "Terraform reference"}
        calls = module.get("module_calls", {})
        if isinstance(calls, dict):
            for name, call in calls.items():
                if isinstance(call, dict):
                    walk(call.get("module", {}), prefix + "module." + name + ".")
    if isinstance(configuration, dict):
        walk(configuration.get("root_module", {}))
    if not edges:
        limits.append("解決できるconfiguration参照がないため、線を作成していません。")
    limits.append("count / for_each の曖昧な展開、module出力、変数経由の関係、depends_onは推測しません。")
    return list(edges.values()), limits
