"""Integer-step sampling; terminal state is retained once at its actual time."""
from fractions import Fraction
import math

class Sampling:
    def __init__(self, seconds, timestep, interval):
        assert math.isfinite(seconds) and seconds >= 0
        assert math.isfinite(timestep) and timestep > 0
        assert math.isfinite(interval) and interval > 0
        duration=Fraction(str(seconds));dt=Fraction(str(timestep))
        ratio=Fraction(str(interval))/dt
        self.steps=math.ceil(duration/dt)
        self.p,self.q=ratio.numerator,ratio.denominator
        self.next_step=0

    def retain(self, step):
        scheduled=step>=self.next_step
        if scheduled:
            next_slot=step*self.q//self.p+1
            self.next_step=(next_slot*self.p+self.q-1)//self.q
        # Bit 1: scheduled; bit 2: actual terminal step. Both share one row.
        return int(scheduled) | (2 if step==self.steps else 0)
