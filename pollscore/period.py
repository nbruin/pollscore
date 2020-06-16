import pandas as pd
import datetime
from pandas._libs.tslibs.timestamps import Timestamp
import re

Period_repr_regex=re.compile(r"Period\('([^']*)', '([^']*)'\)")
very_short_timedelta=pd.to_timedelta("1ms")

class Period(object):
    def __init__(self,a,b=None):
        if isinstance(a,str):
            T = a.split(";")
            if len(T) > 1:
                if len(T) >2 or b is not None:
                    raise ValueError("Ambiguous specification of period length")
                a,b=T
            self.period=pd.Period(a,b)
        elif isinstance(a,datetime.datetime) and isinstance(b,datetime.datetime):
            delta = max(b-a,very_short_timedelta)
            self.period=pd.Period(a,delta)
        else:
            self.period=pd.Period(a,b)
    def __contains__(self,t):
        return self.period.start_time <= t <= self.period.end_time   
    def __str__(self):
        start,freq=Period_repr_regex.search(repr(self.period)).groups()
        if freq[-1] == 'T': freq = freq[:-1]+"min"
        if freq[-1] == 'L': freq = freq[:-1]+"ms"
        if freq == "D" or freq == "H":
            return start
        else:
            return "{}; {}".format(start,freq)
    def __repr__(self):
        s=str(self)
        return "Period('{}')".format(s)
    def __lt__(self,other):
        return self.period.end_time < other.period.start_time
    def __gt__(self,other):
        return self.period.start_time > other.period.end_time
    def __hash__(self):
        return hash(self.period)
    def __eq__(self,other):
        return self.period == other.period
