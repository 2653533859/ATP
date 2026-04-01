"""Tests for global variables API schema."""
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)
sys.modules["app.api.deps"] = types.SimpleNamespace(
    get_current_user=lambda: None,
    require_engineer=lambda: None,
)

from app.models.bootstrap import load_all_models
from app.schemas.global_variable import GlobalVariableCreate, GlobalVariableUpdate, ScopeType


class TestGlobalVariableSchema:
    def test_variable_create_requires_key(self):
        with pytest.raises(Exception):
            GlobalVariableCreate(scope_type=ScopeType.global_scope)

    def test_variable_create_minimal(self):
        var = GlobalVariableCreate(
            scope_type=ScopeType.global_scope,
            key="API_KEY",
            value_encrypted="secret-value",
        )
        assert var.key == "API_KEY"
        assert var.is_secret is False

    def test_variable_create_project_scope(self):
        var = GlobalVariableCreate(
            scope_type=ScopeType.project,
            project_id=5,
            key="DB_PASSWORD",
            value_encrypted="encrypted_password",
            is_secret=True,
            description="Production DB password",
        )
        assert var.scope_type == ScopeType.project
        assert var.project_id == 5
        assert var.is_secret is True

    def test_variable_update_partial(self):
        update = GlobalVariableUpdate(value_encrypted="new_password")
        assert update.value_encrypted == "new_password"
        assert update.key is None

    def test_scope_type_enum(self):
        assert ScopeType.global_scope.value == "global"
        assert ScopeType.project.value == "project"


class TestGlobalVariableReadSerialization:
    def test_serialize_variable_decrypts_plain_values(self, monkeypatch):
        from app.api.v1 import global_variables

        monkeypatch.setattr(global_variables, "decrypt", lambda ciphertext: "https://api.example.com")
        var = types.SimpleNamespace(
            id=1,
            scope_type=ScopeType.global_scope,
            project_id=None,
            key="API_BASE_URL",
            value_encrypted="ciphertext",
            is_secret=False,
            description=None,
            created_at="2026-03-31T00:00:00Z",
            updated_at="2026-03-31T00:00:00Z",
        )

        serialized = global_variables._serialize_variable(var)
        assert serialized.value == "https://api.example.com"

    def test_serialize_variable_masks_by_default_and_can_reveal(self, monkeypatch):
        from app.api.v1 import global_variables

        monkeypatch.setattr(global_variables, "decrypt", lambda ciphertext: "super-secret-token")
        var = types.SimpleNamespace(
            id=2,
            scope_type=ScopeType.global_scope,
            project_id=None,
            key="TOKEN",
            value_encrypted="ciphertext",
            is_secret=True,
            description=None,
            created_at="2026-03-31T00:00:00Z",
            updated_at="2026-03-31T00:00:00Z",
        )

        masked = global_variables._serialize_variable(var)
        revealed = global_variables._serialize_variable(var, reveal_secret=True)

        assert masked.value != "super-secret-token"
        assert revealed.value == "super-secret-token"
