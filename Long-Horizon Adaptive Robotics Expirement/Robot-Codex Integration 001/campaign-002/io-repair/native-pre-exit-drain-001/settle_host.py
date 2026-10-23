"""Use the existing host assessor and settlement, with accurate attribution."""
import importlib.util
from pathlib import Path

path=Path(__file__).resolve().parent.parent/'settle_probe.py'
spec=importlib.util.spec_from_file_location('pre_exit_host_settlement',path)
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
original=prior.load

def load(path,name):
    module=original(path,name)
    if Path(path)==prior.CAMPAIGN/'registry.py':
        common=module.common
        def session15(identifier):
            value=common(identifier);value['author']='Codex session 15';return value
        module.common=module.prior.common=session15
    return module

if __name__=='__main__':
    prior.load=load
    prior.main()
