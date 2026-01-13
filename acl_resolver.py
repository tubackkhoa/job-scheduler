from typing import Any, Optional, TypedDict, Dict, Set, Literal, Union

Role = Literal["admin", "job_editor", "field_editor"]
NodeGlobals = Literal["get_plugins"]
JobGlobals = Literal["apply_value_version_all_jobs"]
FieldGlobals = Literal[
    "create_value_version", "get_value_version", "get_value_versions", "update_value_version"
]


class ACLNodeField(TypedDict):
    roles: Set[Role]
    globals: Optional[Set[FieldGlobals]]


class ACLNodeJob(TypedDict):
    roles: Set[Role]
    globals: Optional[Set[JobGlobals]]
    field: ACLNodeField


class ACLNodePlugin(TypedDict):
    roles: Set[Role]
    globals: Optional[Set[NodeGlobals]]
    job: ACLNodeJob


ACLLevelKey = Literal["plugin", "job", "field"]

ACL_LEVEL: Dict[ACLLevelKey, Optional[ACLLevelKey]] = {
    "plugin": "job",
    "job": "field",
    "field": None,
}

# const mapping, can store and edit in database
ACL_TREE: ACLNodePlugin = {
    "roles": {"admin"},
    "globals": {"get_plugins"},
    "job": {
        "roles": {"admin", "job_editor"},
        "globals": {"apply_value_version_all_jobs"},
        "field": {
            "roles": {"admin", "job_editor", "field_editor"},
            "globals": {
                "create_value_version",
                "get_value_version",
                "get_value_versions",
                "update_value_version",
            },
        },
    },
}


class ACLResolver:
    def __init__(
        self,
        node_globals: Optional[Dict[NodeGlobals, Any]] = None,
        job_globals: Optional[Dict[JobGlobals, Any]] = None,
        field_globals: Optional[Dict[FieldGlobals, Any]] = None,
    ):
        self.globals_map: Dict[ACLLevelKey, Dict] = {
            "plugin": node_globals or {},
            "job": job_globals or {},
            "field": field_globals or {},
        }

    def _collect_allowed(
        self,
        roles: Set[Role],
        level: ACLLevelKey,
        node: Union[ACLNodePlugin, ACLNodeJob, ACLNodeField],
        allowed: Dict[str, Any],
    ) -> None:
        if not roles.isdisjoint(node["roles"]):
            globals_set = node.get("globals")
            if globals_set:
                lookup = self.globals_map[level]
                for g in globals_set:
                    func = lookup.get(g)
                    if func:
                        allowed[g] = func

    def get_allowed_functions(self, roles: Set[Role]) -> Dict[str, Any]:
        allowed: Dict[str, Any] = {}

        self._collect_allowed(roles, "plugin", ACL_TREE, allowed)
        job_node: ACLNodeJob = ACL_TREE["job"]
        self._collect_allowed(roles, "job", job_node, allowed)
        field_node: ACLNodeField = job_node["field"]
        self._collect_allowed(roles, "field", field_node, allowed)

        return allowed
