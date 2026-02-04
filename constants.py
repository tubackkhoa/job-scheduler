from enum import Enum
class ModelEnv(str, Enum):
    staging = "staging"
    production = "production"
    uat = "uat"
    uat_test = "forward_test"
    def __str__(self):
        return self.value