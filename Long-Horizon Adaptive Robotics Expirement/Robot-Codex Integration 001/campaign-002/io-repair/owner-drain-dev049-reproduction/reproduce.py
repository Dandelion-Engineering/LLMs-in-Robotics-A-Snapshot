import asyncio,hashlib,json,sys,tempfile,threading,time,os
from pathlib import Path
from types import SimpleNamespace
h=Path('Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/harness').resolve();sys.path.insert(0,str(h))
import codehost_bridge_v3 as b
async def run():
 with tempfile.TemporaryDirectory(prefix='smoke014-bridge-read-race-') as tmp:
  root=Path(tmp);fixture=SimpleNamespace(evidence=root,run='diagnostic-no-host',client_finishing=threading.Event(),abort_event=threading.Event())
  launches=[]
  async def forbidden(*a,**kw):launches.append(True);raise AssertionError('No host launch allowed')
  bridge=b.Bridge(fixture,owner=object(),launcher=forbidden,retirer=forbidden,sources={})
  class Writer:
   def __init__(self):self.data=bytearray();self.closed=False
   def write(self,data):self.data.extend(data)
   async def drain(self):pass
   def close(self):self.closed=True
  writer=Writer();bridge.process=SimpleNamespace(stdin=writer)
  payload=b'\x00\x00\x04\x03\x00\x00\x00\x00\x01\x00\x00\x00\x08'
  class Reader:
   async def read(self,n):
    marker={'kind':'client_finishing_before_close','schema':'campaign002-client-finishing-1','wall_unix_s':time.time(),'monotonic_s':time.monotonic()}
    with (root/'owner-finishing.json').open('x',encoding='utf-8') as f:json.dump(marker,f);f.flush();os.fsync(f.fileno())
    fixture.client_finishing.set()
    return payload
  channel=b.Channel(1,Reader(),None,{'owner_pid':123});bridge.channels[1]=channel
  channel.h2.feed('upload',b.mux.PREFACE+b'\x00\x00\x00\x04\x00\x00\x00\x00\x00'+b'\x00\x00\x01\x01\x04\x00\x00\x00\x01\x82')
  channel.h2.feed('download',b'\x00\x00\x00\x04\x00\x00\x00\x00\x00')
  sender=asyncio.create_task(bridge.send_frames())
  channel.upload_task=asyncio.create_task(bridge.upload(channel))
  error=None
  try:await channel.upload_task
  except ValueError as exc:
   error=str(exc);bridge.fail('channel_'+type(exc).__name__)
  await sender
  frames=b.mux.FrameParser().feed(bytes(writer.data))
  result={'scope':'Synthetic in-memory scheduling reproduction only; no native process, socket, namespace, model or empirical qualification.',
    'exception_type':'ValueError','exception_reason':error,'synthetic_tail_bytes':len(payload),'synthetic_tail_sha256':hashlib.sha256(payload).hexdigest(),
    'emitted_kinds':[r['kind'] for r in bridge.ledger.events],
    'frames':[{'type':kind,'channel_id':cid,'bytes':len(data)} for kind,cid,data in frames],
    'client_read_bytes':channel.meters['client_read'].summary()['bytes'],'upload_bytes':channel.meters['upload'].summary()['bytes'],
    'queue_bytes_at_close':bridge.budget.total,'stdin_closed':writer.closed,'launch_count':len(launches),
    'frontier_active_stream_ids':channel.finish_frontier['active_stream_ids']}
  assert error=='client_data_after_owner_finish'
  assert result['frames']==[{'type':b.mux.FINISH,'channel_id':0,'bytes':0}]
  assert result['client_read_bytes']==result['upload_bytes']==result['queue_bytes_at_close']==result['launch_count']==0
  print(json.dumps(result))
asyncio.run(run())
