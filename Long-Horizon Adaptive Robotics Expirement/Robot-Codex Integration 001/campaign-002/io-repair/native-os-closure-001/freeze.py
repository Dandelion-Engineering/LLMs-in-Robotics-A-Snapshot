"""Freeze tested diagnostic sources and declare an unexecuted development run."""
import json
import prepare as p


def main():
    value=p.candidate()
    p.common.require(value==p.common.read(p.common.MANIFEST),'Prepared manifest differs')
    p.common.require(not p.common.SNAPSHOT.parent.exists(),'Revision already exists; do not rerun')
    registry=p.load_registry()
    registry.freeze(p.common.MANIFEST,p.common.REVISION)
    p.common.validate(p.common.MANIFEST,p.common.SNAPSHOT)
    p.common.save(p.common.ROOT/'freeze-receipt.json',{'snapshot':p.identity(p.common.SNAPSHOT),
        'archive':p.identity(p.common.SNAPSHOT.with_name('code.zip')),'diagnostic_only':True,
        'previous958_unchanged':True,'original624_unchanged':True,'model_calls':0,'trace_starts':0,
        'state':'prepared_not_launched','requires_next_session_desktop_uac':True})
    print(json.dumps({'frozen':True,'snapshot':p.identity(p.common.SNAPSHOT),'state':'prepared_not_launched'}))


if __name__=='__main__':main()
