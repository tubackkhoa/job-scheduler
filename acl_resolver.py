from typing import Any, Callable, Optional, TypedDict, Dict, Set, Literal

from models import DAO

Role = Literal["admin", "job_editor", "field_editor"]


class ACLNode(TypedDict):
    roles: Set[Role]
    globals: Dict[str, Any]
    children: Optional[Dict[str, "ACLNode"]]


class ACLResolver:
    def __init__(self, db_engine):
        value_version_dao = DAO(db_engine)

        self.tree: Dict[str, ACLNode] = {
            "plugin": {
                "roles": {"admin"},
                "globals": {},
                "children": {
                    "job": {
                        "roles": {"admin", "job_editor"},
                        "globals": {
                            "apply_value_version_all_jobs": value_version_dao.apply_value_version_all_jobs
                        },
                        "children": {
                            "field": {
                                "roles": {"admin", "job_editor", "field_editor"},
                                "globals": {
                                    "create_value_version": value_version_dao.create,
                                    "get_value_version": value_version_dao.get,
                                    "get_value_versions": value_version_dao.list,
                                    "update_value_version": value_version_dao.update,
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
