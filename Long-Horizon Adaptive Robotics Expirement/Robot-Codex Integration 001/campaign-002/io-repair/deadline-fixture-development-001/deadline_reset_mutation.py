import asyncio,sys,unittest
from unittest.mock import patch
import codehost_inside_v3 as inside
import codehost_mux_protocol as mux
from test_codehost_inside_v3 import RelayTests
original=inside.Relay.accept
async def reset_at_finish(self,kind,channel_id,payload):
    if kind==mux.FINISH:
        self.drain_deadline=asyncio.get_running_loop().time()+mux.OWNER_DRAIN_TIMEOUT
    return await original(self,kind,channel_id,payload)
suite=unittest.TestSuite([RelayTests('test_shared_deadline_does_not_restart_at_seal')])
with patch.object(inside.Relay,'accept',reset_at_finish):
    result=unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
