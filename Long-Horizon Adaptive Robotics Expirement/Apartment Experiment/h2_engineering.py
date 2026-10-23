"""Prospective cancellation race fixtures, paired relay, and native preflight."""
import argparse
import asyncio
import copy
import io
from pathlib import Path
import sys
import traceback
import unittest
from unittest import mock
from common import save,canonical

def structural():
    import native_runtime
    import codehost_mux_protocol as mux
    import h2_runtime
    from h2_readback import paired
    from test_codehost_mux_protocol import h2
    cancel=h2(3,0,1,(8).to_bytes(4,'big'))
    def ready(cls=mux.H2Witness):
        w=cls();w.feed('upload',mux.PREFACE+h2(4)+h2(1,5,1,b'x'));w.feed('download',h2(4));return w
    old=ready(h2_runtime.Original);old.feed('upload',cancel)
    try:old.feed('download',h2(1,5,1,b'y'))
    except ValueError as e:assert str(e)=='HTTP/2 headers on unavailable stream'
    else:raise AssertionError('Original cancellation race not reproduced')
    cases=0
    for response in (h2(1,5,1,b'y'),h2(1,4,1,b'y')+h2(0,1,1,b'data'),h2(1,1,1,b'abc')+h2(9,4,1,b'def')):
        for cut in range(len(response)+1):
            a,b=ready(),ready();b.feed('download',response);b.feed('upload',cancel)
            a.feed('download',response[:cut])
            for byte in cancel:a.feed('upload',bytes([byte]))
            a.feed('download',response[cut:]);paired(a.idle_eof(),b.idle_eof())
            # Runtime cancellations do not prevent a later authenticated cleanup.
            a.begin_cleanup('b'*32);b.begin_cleanup('b'*32)
            for w in (a,b):
                w.feed('upload',h2(1,5,3,b'x'));w.feed('upload',h2(3,0,3,(8).to_bytes(4,'big')))
                w.feed('download',h2(1,5,3,b'y'));w.begin_retirement();w.validate_reset_scope()
            paired(a.idle_eof(),b.idle_eof());cases+=1
    rejected=0
    for direction,wire in [('download',cancel),('upload',h2(3,0,1,(1).to_bytes(4,'big'))),('upload',h2(3,0,9,(8).to_bytes(4,'big')))]:
        w=ready()
        try:w.feed(direction,wire)
        except ValueError:rejected+=1
        else:raise AssertionError('Invalid reset accepted')
    for direction,wire in [('upload',cancel),('upload',h2(1,5,1,b'x')),('upload',h2(0,0,1,b'x'))]:
        w=ready();w.feed('upload',cancel)
        try:w.feed(direction,wire)
        except ValueError:rejected+=1
        else:raise AssertionError('Cancelled stream reused')
    w=ready();w.feed('upload',cancel)
    for sid in range(3,131,2):
        w.feed('upload',h2(1,5,sid,b'x'))
        try:w.feed('upload',h2(3,0,sid,(8).to_bytes(4,'big')))
        except ValueError as e:assert sid==129 and 'bound' in str(e);rejected+=1
    assert len(w._runtime_records)==64
    a=ready();a.feed('upload',cancel);a.feed('download',h2(1,5,1,b'y'));good=a.idle_eof()
    for field in ('sha256','frame','error_code'):
        bad=copy.deepcopy(good);bad['runtime_cancel_records'][0]['cancel'][field]='bad'
        try:paired(good,bad)
        except (ValueError,TypeError):rejected+=1
        else:raise AssertionError('Altered cancellation evidence accepted')
    return dict(passed=True,original_race_reproduced=True,fragmented_race_cases=cases,negative_cases=rejected,max_runtime_cancellations=64)

def relay(out):
    import native_runtime,transport
    import codehost_inside_v3 as inside
    sys.modules['inherited_inside']=inside
    import transport_inside
    import test_codehost_bridge_v3 as fixture
    from h2_readback import paired
    h2=fixture.h2;m=fixture.m
    class Tests(fixture.BridgeTests):
        async def runtime(self,race):
            self.host_options={'reply':h2(4)}
            async def body():
                reader,writer,_=self.client();await writer.received.wait()
                held=asyncio.Event();release=asyncio.Event();send=self.process.relay.send
                response=h2(1,5,1,b'late')
                async def delayed(kind,channel,payload=b'',account=True):
                    if race and kind==m.DATA and payload==response:held.set();await release.wait()
                    await send(kind,channel,payload,account)
                self.process.relay.send=delayed
                if race:self.process.hosts[0][0].feed_data(response);await held.wait()
                reader.feed_data(h2(3,0,1,(8).to_bytes(4,'big')))
                while not self.process.relay.channels[1].h2.summary()['runtime_cancel_records']:await asyncio.sleep(0)
                if race:release.set()
                else:self.process.hosts[0][0].feed_data(response)
                while len(writer.data)<len(h2(4)+response):await asyncio.sleep(0)
                await asyncio.to_thread(self.fixture.native_cleanup_barrier,fixture.cleanup_seed())
            receipt=await self.run_bridge(body);channel=receipt['channels'][0]
            assert receipt['qualified'] and receipt['queued_bytes_at_close']==0
            proof=paired(channel['h2'],channel['namespace_closed']['h2']);assert proof['runtime_cancellations']==1
            assert channel['meters']['client_read']==channel['namespace_closed']['upload']
            assert channel['meters']['client_written']==channel['namespace_closed']['download']
            save(out/('race.json' if race else 'late.json'),receipt)
        async def test_runtime_late(self):await self.runtime(False)
        async def test_runtime_race(self):await self.runtime(True)
    suite=unittest.TestSuite(Tests(name) for name in ('test_runtime_late','test_runtime_race','test_cleanup_active_cancel_original_bytes_and_late_response','test_cleanup_active_normal_endpoint_race_preserves_raw_classification'))
    stream=io.StringIO()
    # storage_engineering may already have imported the adapter against a
    # separately loaded copy of the original namespace module. Bind both
    # fixture endpoints explicitly so suite order cannot select the old relay.
    with (mock.patch.object(fixture.bridge,'Bridge',transport.Bridge),
          mock.patch.object(inside,'Metadata',transport_inside.Metadata),
          mock.patch.object(inside,'Relay',transport_inside.Relay)):
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (out/'tests.txt').write_text(stream.getvalue(),encoding='utf-8');assert result.wasSuccessful(),stream.getvalue()
    return dict(passed=True,tests=result.testsRun)

def run(out):
    out.mkdir(parents=True,exist_ok=False);result=dict(passed=False,stage='runtime-http2-cancel-proof',official_sessions=0,checks={},evidence={})
    try:
        result['evidence']['structural']=structural();result['checks']['structural_and_negatives']=True
        result['evidence']['relay']=relay(out);result['checks']['actual_paired_relay']=True
        import integration_engineering
        result['checks']['both_native_preflights']=integration_engineering.run(out/'preflight')
        result['passed']=all(result['checks'].values())
    except BaseException as e:result.update(error=repr(e),traceback=traceback.format_exc())
    save(out/'result.json',result);print(canonical(result).decode());return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
