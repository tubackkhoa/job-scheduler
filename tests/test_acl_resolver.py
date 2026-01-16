import os
import tempfile
import pytest
from unittest.mock import MagicMock
from casbin.persist.adapters import FileAdapter

from acl_resolver import ACLResolver
from enforcer import ExecutionContext


# --------------------
# Fixtures
# --------------------


@pytest.fixture
def dao():
    dao = MagicMock()
    dao.get_all_plugins = MagicMock(name="get_all_plugins")
    dao.apply_value_version_all_jobs = MagicMock()
    dao.get_jobs_by_plugin_and_session = MagicMock()
    dao.create_value_version = MagicMock()
    dao.get_value_version = MagicMock()
    dao.get_value_versions = MagicMock()
    dao.update_value_version = MagicMock()
    return dao


@pytest.fixture
def adapter():
    fd, path = tempfile.mkstemp()
    os.close(fd)

    yield FileAdapter(path)

    os.remove(path)


@pytest.fixture
def acl_resolver(dao, adapter):
    return ACLResolver(dao=dao, adapter=adapter)


# --------------------
# Helpers
# --------------------


def make_ctx(allowed_permissions: set[str], is_admin: bool = False) -> ExecutionContext:
    ctx = MagicMock(spec=ExecutionContext)

    def allowed(permission: str, action: str = "execute") -> bool:
        return permission in allowed_permissions

    ctx.allowed.side_effect = allowed
    ctx.is_admin.return_value = is_admin
    return ctx


# --------------------
# Tests
# --------------------


def test_admin_has_all_permissions(acl_resolver):
    ctx = make_ctx(set(), is_admin=True)

    allowed = acl_resolver.get_allowed_functions(ctx)

    assert "apply_value_version_all_jobs" in allowed
    assert "create_value_version" in allowed
    assert "get_value_version" in allowed
    assert "get_value_versions" in allowed
    assert "update_value_version" in allowed


def test_job_permissions(acl_resolver):
    ctx = make_ctx({"job"})

    allowed = acl_resolver.get_allowed_functions(ctx)

    assert "apply_value_version_all_jobs" in allowed
    assert "create_value_version" not in allowed


def test_field_permissions(acl_resolver):
    ctx = make_ctx({"field"})

    allowed = acl_resolver.get_allowed_functions(ctx)

    assert "create_value_version" in allowed
    assert "get_value_version" in allowed
    assert "get_value_versions" in allowed
    assert "update_value_version" in allowed
    assert "apply_value_version_all_jobs" not in allowed


def test_unknown_permission_gets_nothing(acl_resolver):
    ctx = make_ctx({"unknown"})

    allowed = acl_resolver.get_allowed_functions(ctx)

    assert allowed == {}


def test_multiple_permissions_merge(acl_resolver):
    ctx = make_ctx({"job", "field"})

    allowed = acl_resolver.get_allowed_functions(ctx)

    assert "apply_value_version_all_jobs" in allowed
    assert "create_value_version" in allowed


def test_allowed_functions_are_callable(acl_resolver):
    ctx = make_ctx(set(), is_admin=True)

    allowed = acl_resolver.get_allowed_functions(ctx)

    for name, fn in allowed.items():
        assert callable(fn), f"{name} is not callable"
