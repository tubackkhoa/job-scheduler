import pytest
from typing import Set
from unittest.mock import MagicMock

from acl_resolver import ACLResolver, Role


@pytest.fixture
def node_globals():
    return {"get_plugins": MagicMock(name="get_plugins_func")}


@pytest.fixture
def job_globals():
    return {"apply_value_version_all_jobs": MagicMock(name="apply_value_version_all_jobs_func")}


@pytest.fixture
def field_globals():
    return {
        "create_value_version": MagicMock(name="create_value_version_func"),
        "get_value_version": MagicMock(name="get_value_version_func"),
        "get_value_versions": MagicMock(name="get_value_versions_func"),
        "update_value_version": MagicMock(name="update_value_version_func"),
    }


@pytest.fixture
def acl_resolver(node_globals, job_globals, field_globals):
    return ACLResolver(
        node_globals=node_globals,
        job_globals=job_globals,
        field_globals=field_globals,
    )


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
