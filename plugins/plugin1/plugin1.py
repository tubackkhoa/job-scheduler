

import pluggy
from pydantic import BaseModel

PROJECT_NAME = "alpha-miner"

hookimpl = pluggy.HookimplMarker(PROJECT_NAME)

class Config(BaseModel):    
    version: str = "1.0"

class Plugin1():
    
    @hookimpl
    def init(self, config):               
        self.config = Config.model_validate(config)       

    @hookimpl
    def migrate(self, new_config):        
        # transform config first
        self.config = Config.model_validate(new_config)       

    @hookimpl
    def schema(self):        
        return Config.model_json_schema()

    @hookimpl
    async def run(self):        
        return self.config