
import pluggy

PROJECT_NAME = "alpha-miner"

hookimpl = pluggy.HookimplMarker(PROJECT_NAME)

class Plugin2:
    @hookimpl
    def init(self, config):        
        self.config = config      

    @hookimpl
    def migrate(self, new_config):        
        self.config = new_config   

    @hookimpl
    async def run(self):        
        return self.config