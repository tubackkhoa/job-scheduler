import pytest
from typing import Set
from unittest.mock import MagicMock

from acl_resolver import ACLResolver, Role


@pytest.fixture
def mock_db_engine():
    return MagicMock()


@pytest.fixture
def acl_resolver(mock_db_engine):
    return ACLResolver(mock_db_engine)


def test_admin_has_all_permissions(acl_resolver):
    roles: Set[Role] = {"admin"}

    allowed = acl_resolver.get_allowed_functions(roles)

    assert "apply_value_version_all_jobs" in allowed
    assert "create_value_version" in allowed
    assert "get_value_version" in allowed
    assert "get_value_versions" in allowed
    assert "update_value_version" in allowed


def test_job_editor_permissions(acl_resolver):
    roles: Set[Role] = {"job_editor"}

    allowed = acl_resolver.get_allowed_functions(roles)

    assert "apply_value_version_all_jobs" in allowed

    assert "create_value_version" in allowed
    assert "get_value_version" in allowed
    assert "get_value_versions" in allowed
    assert "update_value_version" in allowed


def test_field_editor_permissions(acl_resolver):
    roles: Set[Role] = {"field_editor"}

    allowed = acl_resolver.get_allowed_functions(roles)

    assert "create_value_version" in allowed
    assert "get_value_version" in allowed
    assert "get_value_versions" in allowed
    assert "update_value_version" in allowed

    assert "apply_value_version_all_jobs" not in allowed


def test_unknown_role_gets_nothing(acl_resolver):
    roles = {"unknown"}  # type: ignore

    allowed = acl_resolver.get_allowed_functions(roles)

    assert allowed == {}


def test_multiple_roles_merge_permissions(acl_resolver):
    roles: Set[Role] = {"job_editor", "field_editor"}

    allowed = acl_resolver.get_allowed_functions(roles)

    assert "apply_value_version_all_jobs" in allowed
    assert "create_value_version" in allowed


def test_allowed_functions_are_callable(acl_resolver):
    roles: Set[Role] = {"admin"}

    allowed = acl_resolver.get_allowed_functions(roles)

    for name, fn in allowed.items():
        assert callable(fn), f"{name} is not callable"
