"""Protected job schedule; only current task is exposed in a public packet."""
import random

class Schedule:
    def __init__(self,seed,encounters=3):
        if encounters<3:raise ValueError('At least three C encounters required')
        randomizer=random.Random(seed);self.jobs=[];version=0;destinations={'A1':'inspection','B2':'parking2'}
        for encounter in range(encounters):
            if encounter:
                for _ in range(randomizer.randint(2,3)):
                    part=randomizer.choice(['A1','B2']);dest=destinations[part]
                    version+=1;self.jobs.append({'version':version,'kind':'AB-transfer','part_id':part,'destination':dest,'requirements':[]})
                    destinations[part]='parking1' if dest=='inspection' else 'inspection' if part=='A1' else ('quarantine' if dest=='parking2' else 'parking2')
            version+=1;self.jobs.append({'version':version,'kind':'C-placement','part_id':'C1','destination':'C_pad','requirements':[]})
        self.index=0

    @property
    def current(self):return dict(self.jobs[self.index])
    def advance(self):
        if self.index+1>=len(self.jobs):return None
        self.index+=1;return self.current
