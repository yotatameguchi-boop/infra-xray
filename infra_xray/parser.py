"""Versioned plan validation and safe resource projection."""
import json
import re
from pathlib import Path
from .sanitizer import FIELDS, sanitize
from .rules import diagnose
from .graph import build_edges

class PlanError(ValueError):
    pass

ACTIONS = {("create",): "create", ("update",): "update", ("delete",): "delete", ("no-op",): "no-change", ("read",): "read", ("delete", "create"): "replace", ("create", "delete"): "replace"}

def load_plan(path):
    try:
        if Path(path).stat().st_size > 50 * 1024 * 1024:
            raise PlanError("JSONは50 MiB以下にしてください。")
        with open(path, encoding="utf-8-sig") as file:
            data = json.load(file)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
        raise PlanError("JSONを読み込めません。ファイルとJSON形式を確認してください。") from None
    return analyze(data)

def analyze(data):
    if not isinstance(data, dict):
        raise PlanError("Terraform plan JSONオブジェクトが必要です。")
    version = data.get("format_version")
    if not isinstance(version, str) or not re.fullmatch(r"1\.\d+", version):
        raise PlanError("未対応のformat_versionです。1.xのplan JSONを指定してください。")
    terraform = data.get("terraform_version")
    if not isinstance(terraform, str) or not re.fullmatch(r"1\.\d+\.\d+(?:[-+][\w.-]+)?", terraform):
        raise PlanError("Terraform 1.xのplan JSONを指定してください。")
    if "planned_values" not in data or not isinstance(data["planned_values"], dict):
        raise PlanError("planned_values がありません。stateではなく terraform show -json のplan出力が必要です。")
    changes = data.get("resource_changes", [])
    if not isinstance(changes, list):
        raise PlanError("resource_changes の形式が不正です。")
    nodes, ids, ignored = [], set(), 0
    for item in changes:
        if not isinstance(item, dict) or not isinstance(item.get("type"), str):
            raise PlanError("リソース情報の形式が不正です。")
        kind, address, change = item["type"], item.get("address"), item.get("change")
        if not isinstance(address, str) or not address or len(address) > 1024 or not isinstance(change, dict):
            raise PlanError("リソースのaddress / changeが不正です。")
        if address in ids:
            raise PlanError("リソースのaddressが重複しています。")
        ids.add(address)
        actions = change.get("actions")
        if not isinstance(actions, list) or any(not isinstance(a, str) for a in actions) or tuple(actions) not in ACTIONS:
            raise PlanError("未対応の変更操作です。")
        for side in ("before", "after"):
            if change.get(side) is not None and not isinstance(change[side], dict):
                raise PlanError("変更前後の値はオブジェクトである必要があります。")
        if kind not in FIELDS or item.get("mode", "managed") != "managed":
            ignored += 1
            continue
        node = {"id": address, "name": address.split(".")[-1], "type": kind, "action": ACTIONS[tuple(actions)],
                "before": sanitize(kind, change.get("before"), change.get("before_sensitive", False)),
                "after": sanitize(kind, change.get("after"), change.get("after_sensitive", False), change.get("after_unknown", False))}
        node["findings"], node["limitations"] = diagnose(node)
        nodes.append(node)
    # Unchanged resources can be absent from resource_changes.
    def visit(module):
        nonlocal ignored
        if not isinstance(module, dict):
            raise PlanError("planned_valuesのmodule形式が不正です。")
        resources, children = module.get("resources", []), module.get("child_modules", [])
        if not isinstance(resources, list) or not isinstance(children, list):
            raise PlanError("planned_valuesのリソース形式が不正です。")
        for item in resources:
            if not isinstance(item, dict):
                raise PlanError("planned_valuesのリソース形式が不正です。")
            address, kind = item.get("address"), item.get("type")
            if not isinstance(address, str) or not isinstance(kind, str):
                raise PlanError("planned_valuesのaddress / typeが不正です。")
            if address in ids:
                continue
            ids.add(address)
            if kind not in FIELDS or item.get("mode", "managed") != "managed":
                ignored += 1
                continue
            values = sanitize(kind, item.get("values"), item.get("sensitive_values", False))
            nodes.append({"id": address, "name": address.split(".")[-1], "type": kind, "action": "no-change", "before": values, "after": values, "findings": [], "limitations": []})
        for child in children:
            visit(child)
    visit(data["planned_values"].get("root_module", {}))
    edges, graph_limits = build_edges(data.get("configuration", {}), nodes)
    return {"schemaVersion": 1, "terraformVersion": terraform, "formatVersion": version, "nodes": nodes, "edges": edges,
            "findings": [f for n in nodes for f in n["findings"]],
            "limitations": ["診断はSG-001 / DB-001 / OPS-001のみです。警告がない場合も安全性を保証しません。", "線はTerraformの参照関係を表し、ネットワーク通信経路ではありません。", "IPv6、既存の公開設定、実際の到達性は評価対象外です。"] + graph_limits,
            "ignoredResources": ignored}
