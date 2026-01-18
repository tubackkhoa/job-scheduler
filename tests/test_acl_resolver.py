import os
import tempfile
import pytest
from unittest.mock import MagicMock
from casbin.persist.adapters import FileAdapter

from acl_resolver import ACLResolver
from enforcer import ExecutionContext


# --------------------
# Permission sentinels (NO enums assumed)
# --------------------

JOB_PERMISSION = object()
FIELD_PERMISSION = object()


# --------------------
# Fixtures
# --------------------


@pytest.fixture
def adapter():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    yield FileAdapter(path)
    os.remove(path)


# --------------------
# Dummy ACL target functions
# --------------------


def apply_value_version_all_jobs():
    pass


def create_value_version():
    pass


def get_value_version():
    pass


def get_value_versions():
    pass


def update_value_version():
    pass


# --------------------
# Permission map
# --------------------


@pytest.fixture
def permission_map():
    return {
        JOB_PERMISSION: {
            apply_value_version_all_jobs,
        },
        FIELD_PERMISSION: {
            create_value_version,
            get_value_version,
            get_value_versions,
            update_value_version,
        },
    }


@pytest.fixture
def acl_resolver(permission_map, adapter):
    return ACLResolver(permission_map=permission_map, adapter=adapter)


# --------------------
# Helpers
# --------------------


def make_ctx(allowed_permissions: set, is_admin: bool = False) -> ExecutionContext:
    ctx = MagicMock(spec=ExecutionContext)
    ctx.allowed.side_effect = lambda p: p in allowed_permissions
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
    ctx = make_ctx({JOB_PERMISSION})
    allowed = acl_resolver.get_allowed_functions(ctx)

    assert "apply_value_version_all_jobs" in allowed
    assert "create_value_version" not in allowed


def test_field_permissions(acl_resolver):
    ctx = make_ctx({FIELD_PERMISSION})
    allowed = acl_resolver.get_allowed_functions(ctx)

    assert "create_value_version" in allowed
    assert "get_value_version" in allowed
    assert "get_value_versions" in allowed
    assert "update_value_version" in allowed
    assert "apply_value_version_all_jobs" not in allowed


def test_unknown_permission_gets_nothing(acl_resolver):
    ctx = make_ctx({object()})
    allowed = acl_resolver.get_allowed_functions(ctx)

    assert allowed == {}


def test_multiple_permissions_merge(acl_resolver):
    ctx = make_ctx({JOB_PERMISSION, FIELD_PERMISSION})
    allowed = acl_resolver.get_allowed_functions(ctx)

    assert "apply_value_version_all_jobs" in allowed
    assert "create_value_version" in allowed


def test_allowed_functions_are_callable(acl_resolver):
    ctx = make_ctx(set(), is_admin=True)
    allowed = acl_resolver.get_allowed_functions(ctx)

    for name, fn in allowed.items():
        assert callable(fn), f"{name} is not callable"
