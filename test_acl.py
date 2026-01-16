from acl_resolver import ACLResolver
from enforcer import (
    ExecutionContext,
    Subject,
    create_enforcer,
    require,
)
from models import DAO
from plugin_manager import PluginManager


package = "plugins.quant_engine_management_plugin.Plugin"
PluginManager.acl_resolver = ACLResolver(DAO("sqlite:///:memory:?check_same_thread=false"))
plugin = PluginManager.load_plugin(package)


ctx_denied = PluginManager.create_ctx(
    package,
    Subject(
        user_id="alice",
        roles={"role:user"},
        groups={"group:other"},
    ),
)

# ✅ User with permission
ctx_allowed = PluginManager.create_ctx(
    package,
    Subject(
        user_id="bob",
        roles={"role:user"},
        groups={"group:data"},
    ),
)

template_str = "{{fetch_data()}}"
engine = plugin.env().from_string(template_str)


print(engine.render(ctx=ctx_allowed))
try:
    print(engine.render(ctx=ctx_denied))
except Exception as e:
    print(e)
