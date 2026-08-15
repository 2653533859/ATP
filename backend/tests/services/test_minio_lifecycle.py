import json

import pytest
from minio.commonconfig import Filter
from minio.lifecycleconfig import Expiration, LifecycleConfig, Rule

from app import ops_minio_lifecycle as lifecycle


def test_parse_expiration_rules_requires_scoped_prefix_and_bounded_days():
    result = lifecycle.parse_expiration_rules(json.dumps([{"id": "scratch", "prefix": "tmp/", "days": 7}]))
    assert result == [lifecycle.ExpirationRuleSpec(rule_id="scratch", prefix="tmp/", days=7)]

    for payload in (
        json.dumps([{"id": "all", "prefix": "", "days": 7}]),
        json.dumps([{"id": "root", "prefix": "/", "days": 7}]),
        json.dumps([{"id": "too-old", "prefix": "tmp/", "days": 3651}]),
    ):
        with pytest.raises(ValueError):
            lifecycle.parse_expiration_rules(payload)


def test_merge_lifecycle_config_preserves_foreign_rules_and_replaces_owned_rules():
    foreign = Rule("Enabled", expiration=Expiration(days=90), rule_filter=Filter(prefix="reports/"), rule_id="vendor")
    old_owned = Rule(
        "Enabled",
        expiration=Expiration(days=1),
        rule_filter=Filter(prefix="tmp/"),
        rule_id="atp-managed-expiration-old",
    )
    existing = LifecycleConfig([foreign, old_owned])

    managed = lifecycle.build_managed_rules(
        2,
        [lifecycle.ExpirationRuleSpec(rule_id="scratch", prefix="tmp/", days=7)],
    )
    merged = lifecycle.merge_lifecycle_config(existing, managed)

    assert [rule.rule_id for rule in merged.rules] == [
        "vendor",
        "atp-managed-abort-incomplete-multipart",
        "atp-managed-expiration-scratch",
    ]
    assert merged.rules[0].expiration.days == 90


def test_reconcile_lifecycle_writes_merged_config():
    class FakeClient:
        def __init__(self):
            self.config = None

        def get_bucket_lifecycle(self, _bucket):
            return self.config

        def set_bucket_lifecycle(self, _bucket, config):
            self.config = config

    client = FakeClient()
    result = lifecycle.reconcile_lifecycle(
        client,
        "atp",
        abort_days=1,
        expiration_rules=[],
    )

    assert result == {"preserved_rules": 0, "managed_rules": 1}
    assert client.config.rules[0].rule_id == "atp-managed-abort-incomplete-multipart"
