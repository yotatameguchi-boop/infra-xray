"""Strict projection. Never forward arbitrary Terraform values to the UI."""
import re

FIELDS = {
    "aws_instance": {"instance_type", "subnet_id", "vpc_security_group_ids", "associate_public_ip_address"},
    "aws_security_group": {"vpc_id", "ingress"},
    "aws_vpc_security_group_ingress_rule": {"security_group_id", "cidr_ipv4", "from_port", "to_port", "ip_protocol"},
    "aws_db_instance": {"publicly_accessible", "encrypted", "storage_encrypted", "deletion_protection", "port", "multi_az", "vpc_security_group_ids"},
    "aws_vpc": {"cidr_block", "enable_dns_support", "enable_dns_hostnames"},
    "aws_subnet": {"vpc_id", "cidr_block", "map_public_ip_on_launch"},
    "aws_lb": {"internal", "load_balancer_type", "security_groups", "subnets"},
}
RULE_FIELDS = {"from_port", "to_port", "protocol", "cidr_blocks"}
REDACTED = "[sensitive]"
UNKNOWN = "[unknown]"
UNAVAILABLE = "[unavailable]"

def mask_at(mask, key):
    if mask is True:
        return True
    if isinstance(mask, dict):
        return mask.get(key, False)
    if isinstance(mask, list) and isinstance(key, int) and key < len(mask):
        return mask[key]
    return False

def project(value, sensitive=False, unknown=False, fields=None):
    if sensitive is True or not isinstance(sensitive, (bool, dict, list)):
        return REDACTED
    if unknown is True or not isinstance(unknown, (bool, dict, list)):
        return UNKNOWN
    for mask, marker in ((sensitive, REDACTED), (unknown, UNKNOWN)):
        if isinstance(mask, dict) and mask and not isinstance(value, dict):
            return marker
        if isinstance(mask, list) and mask and not isinstance(value, list):
            return marker
    if isinstance(value, dict):
        keys = set(value)
        if isinstance(unknown, dict):
            keys |= set(unknown)
        return {k: project(value.get(k), mask_at(sensitive, k), mask_at(unknown, k), RULE_FIELDS if k == "ingress" else None)
                for k in sorted(keys) if fields is not None and k in fields}
    if isinstance(value, list):
        return [project(v, mask_at(sensitive, i), mask_at(unknown, i), fields) for i, v in enumerate(value)]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return UNAVAILABLE

def sanitize(resource_type, value, sensitive=False, unknown=False):
    if sensitive is True or not isinstance(sensitive, (bool, dict, list)):
        return {"_status": REDACTED}
    if unknown is True or not isinstance(unknown, (bool, dict, list)):
        return {"_status": UNKNOWN}
    if value is None and not unknown:
        return {}
    if not isinstance(value, dict) and value is not None:
        return {"_status": UNAVAILABLE}
    return project(value or {}, sensitive, unknown, FIELDS.get(resource_type, set()))
