"""Rules operate only on sanitized values and use three-valued logic."""
from .sanitizer import REDACTED, UNKNOWN, UNAVAILABLE

BLOCKED = (REDACTED, UNKNOWN, UNAVAILABLE)

def ssh_rule(rule, standalone=False):
    if not isinstance(rule, dict):
        return None
    protocol = rule.get("ip_protocol" if standalone else "protocol")
    cidrs = rule.get("cidr_ipv4") if standalone else rule.get("cidr_blocks")
    if standalone:
        cidrs = [cidrs] if isinstance(cidrs, str) and cidrs not in BLOCKED else None
    if not isinstance(cidrs, list):
        return None
    public = "0.0.0.0/0" in cidrs
    if not public:
        return None if any(c in BLOCKED for c in cidrs if isinstance(c, str)) else False
    if protocol in ("-1", -1):
        return True
    if protocol not in ("tcp", "6", 6):
        return None if protocol is None or protocol in BLOCKED else False
    low, high = rule.get("from_port"), rule.get("to_port")
    if type(low) is not int or type(high) is not int:
        return None
    return low <= 22 <= high

def ssh_state(values, standalone=False):
    if "_status" in values:
        return None
    if standalone:
        return ssh_rule(values, True)
    ingress = values.get("ingress")
    if not isinstance(ingress, list):
        return None
    states = [ssh_rule(r) for r in ingress]
    return True if True in states else (None if None in states else False)

def diagnose(node):
    findings, limitations = [], []
    action, kind = node["action"], node["type"]
    before, after = node["before"], node["after"]
    def add(rule, title, reason, evidence):
        findings.append({"id": rule, "resource": node["id"], "title": title, "reason": reason, "evidence": evidence, "severity": "high" if rule != "OPS-001" else "warning", "limitations": "設定上の確認事項です。実際の到達性、IAM、NACL、バックアップ状態は評価しません。"})
    if kind == "aws_db_instance" and action in ("delete", "replace"):
        add("OPS-001", "RDSの削除・置換予定", "データ消失やサービス停止の可能性があります。バックアップと復旧手順を確認してください。", "change.actions に delete が含まれています。")
    if action not in ("create", "update", "replace"):
        return findings, limitations
    if kind == "aws_db_instance":
        old = False if action == "create" else before.get("publicly_accessible")
        new = after.get("publicly_accessible")
        if new is True and old is False:
            add("DB-001", "RDSのパブリックアクセスが有効化", "外部公開の必要性と関連するセキュリティグループを確認してください。", "publicly_accessible: false（またはリソース未作成） → true")
        elif type(old) is not bool or type(new) is not bool:
            limitations.append("DB-001: publicly_accessible が unknown / sensitive / 欠落のため変更を確定できません。")
    if kind in ("aws_security_group", "aws_vpc_security_group_ingress_rule"):
        standalone = kind.endswith("ingress_rule")
        old = False if action == "create" else ssh_state(before, standalone)
        new = ssh_state(after, standalone)
        if old is False and new is True:
            add("SG-001", "SSHの許可元が全IPv4へ拡大", "全IPv4アドレスからTCP/22を許可する設定です。許可元の制限を確認してください。", "変更前: 全IPv4へのSSH許可なし → 変更後: 0.0.0.0/0、TCP/22を含むポート範囲（または全プロトコル）")
        elif old is None or new is None:
            limitations.append("SG-001: ingress / CIDR / protocol / port が unknown / sensitive / 欠落のため変更を確定できません。")
    return findings, limitations
