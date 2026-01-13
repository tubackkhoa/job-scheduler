from typing import Any, Optional, TypedDict, Dict, Set, Literal, Union


Role = Literal["admin", "job_editor", "field_editor"]
PluginGlobals = Literal["get_all_plugins"]
JobGlobals = Literal[
    "apply_value_version_all_jobs",
    "get_jobs_by_plugin_and_session",
    "list_trade_models",
    "create_trade_model",
    "deactivate_trade_model",
]
FieldGlobals = Literal[
    "create_value_version",
    "get_value_version",
    "get_value_versions",
    "update_value_version",
]


class ACLNode(TypedDict):
    roles: Set[Role]
    globals: Optional[Set[str]]


class ACLNodeField(ACLNode):
    globals: Optional[Set[FieldGlobals]]


class ACLNodeJob(ACLNode):
    globals: Optional[Set[JobGlobals]]


class ACLNodePlugin(ACLNode):
    globals: Optional[Set[PluginGlobals]]


class AclTree(TypedDict):
    plugin: ACLNodePlugin
    job: ACLNodeJob
    field: ACLNodeField


# Flat ACL dictionary
ACL_TREE: AclTree = {
    "plugin": {
        "roles": {"admin"},
        "globals": {"get_all_plugins"},
    },
    "job": {
        "roles": {"admin", "job_editor"},
        "globals": {
            "apply_value_version_all_jobs",
            "get_jobs_by_plugin_and_session",
            "list_trade_models",
            "create_trade_model",
            "deactivate_trade_model",
        },
    },
    "field": {
        "roles": {"admin", "job_editor", "field_editor"},
        "globals": {
            "create_value_version",
            "get_value_version",
            "get_value_versions",
            "update_value_version",
        },
    },
}


class ACLResolver:
    def __init__(
        self,
        plugin_globals: Optional[Dict[PluginGlobals, Any]] = None,
        job_globals: Optional[Dict[JobGlobals, Any]] = None,
        field_globals: Optional[Dict[FieldGlobals, Any]] = None,
    ):
        self.globals_map = {
            "plugin": plugin_globals or {},
            "job": job_globals or {},
            "field": field_globals or {},
        }

    def get_allowed_functions(self, roles: Set[Role]) -> Dict[str, Any]:
        allowed: Dict[str, Any] = {}

        for level in ACL_TREE.keys():  # type: ignore
            node: ACLNode = ACL_TREE[level]
            if not roles.isdisjoint(node["roles"]):
                globals_set = node.get("globals")
                if globals_set:
                    lookup = self.globals_map[level]
                    for g in globals_set:
                        func = lookup.get(g)
                        if func:
                            allowed[g] = func

        return allowed
