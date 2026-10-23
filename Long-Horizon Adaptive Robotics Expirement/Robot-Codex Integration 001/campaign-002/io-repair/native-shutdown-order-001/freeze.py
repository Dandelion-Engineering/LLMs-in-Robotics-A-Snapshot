"""One fresh source archive and atomic map registration, never an execution."""
import json
import prepare as p

def main():
    value, changed = p.candidate()
    p.common.require(value == p.common.read(p.common.MANIFEST), 'Prepared manifest changed')
    p.common.require(not p.common.SNAPSHOT.parent.exists(), 'Revision already exists; reconcile')
    registry = p.load(p.CAMPAIGN/'registry.py', 'ordered_diagnostic_registry')
    original = registry.common
    def session15(identifier):
        value = original(identifier);value['author']='Codex session 15';return value
    registry.common = registry.prior.common = session15
    result = registry.freeze(p.common.MANIFEST, p.common.REVISION)
    p.common.validate(p.common.MANIFEST, p.common.SNAPSHOT)
    p.common.save(p.common.ROOT/'freeze-receipt.json', {
        'snapshot':p.identity(p.common.SNAPSHOT),'archive':p.identity(p.common.SNAPSHOT.with_name('code.zip')),
        'shared_source_changes':changed,'original624_verified':True,'diagnostic_only':True})
    print(json.dumps({'snapshot':p.identity(p.common.SNAPSHOT)}))

if __name__ == '__main__': main()
