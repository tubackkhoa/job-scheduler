from typing import Any, Callable, Optional, TypedDict, Dict, Set, Literal

from models import DAO

Role = Literal["admin", "job_editor", "field_editor"]


class ACLNode(TypedDict):
    roles: Set[Role]
    globals: Dict[str, Any]
    children: Optional[Dict[str, "ACLNode"]]


class ACLResolver:
    def __init__(self, dao: DAO):

        self.tree: Dict[str, ACLNode] = {
            "plugin": {
                "roles": {"admin"},
                "globals": {},
                "children": {
                    "job": {
                        "roles": {"admin", "job_editor"},
                        "globals": {
                            "apply_value_version_all_jobs": dao.apply_value_version_all_jobs
                        },
                        "children": {
                            "field": {
                                "roles": {"admin", "job_editor", "field_editor"},
                                "globals": {
                                    "create_value_version": dao.create_value_version,
                                    "get_value_version": dao.get_value_version,
                                    "get_value_versions": dao.get_value_versions,
                                    "update_value_version": dao.update_value_version,
                                },
                                "children": {},
                            }
                        },
                    }
                },
            }
        }

    def get_allowed_functions(
        self,
        roles: Set[Role],
    ) -> Dict[str, Callable]:
        allowed: Dict[str, Callable] = {}
        self._walk(self.tree, roles, allowed)
        return allowed

    def _walk(
        self,
        node: Dict[str, ACLNode],
        roles: Set[Role],
        allowed: Dict[str, Any],
    ) -> None:
        for data in node.values():
            if roles & data["roles"]:
                allowed.update(data["globals"])

            children = data.get("children")
            if children:
                self._walk(children, roles, allowed)
