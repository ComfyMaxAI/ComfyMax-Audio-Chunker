"""Optional stem-energy suggestions. Never reads lyrics or changes boundaries."""
from ..regions import activity

TYPES=('Vocal','Instrumental')


class VocalActivity:
    def __init__(self,arrays,rate):
        self.available='vocals' in arrays
        self.spans=[]
        if self.available:
            spans,_=activity(arrays['vocals'],arrays['mix'],rate)
            self.spans=[(round(a*rate),round(b*rate)) for a,b in spans]

    def __call__(self,start,end):
        if not self.available: return 'Vocal'
        active=sum(max(0,min(end,b)-max(start,a)) for a,b in self.spans)
        return 'Vocal' if active>=.1*(end-start) and active>0 else 'Instrumental'


def suggested(start,end,classifier=None):
    return dict(start_frame=start,end_frame=end,type=classifier(start,end) if classifier else 'Vocal',
                source='suggested' if classifier and getattr(classifier,'available',True) else 'default')


def reconcile(old,bounds,classifier=None):
    result=[]
    for start,end in zip(bounds,bounds[1:]):
        exact=next((r for r in old if r['start_frame']==start and r['end_frame']==end),None)
        if exact:
            result.append(dict(exact)); continue
        manual=[r for r in old if r['source']=='manual' and r['start_frame']<end and r['end_frame']>start]
        if manual:
            # Ties choose the earlier interval. A new interval has one type;
            # preserve the user's choice over a fresh automatic suggestion.
            winner=max(manual,key=lambda r:(min(end,r['end_frame'])-max(start,r['start_frame']),-r['start_frame']))
            result.append(dict(start_frame=start,end_frame=end,type=winner['type'],source='manual'))
        else: result.append(suggested(start,end,classifier))
    return result


def validate_interval_types(records,bounds):
    if not isinstance(records,list) or len(records)!=len(bounds)-1:
        raise ValueError('Interval types must cover every consecutive marker interval')
    for r,a,b in zip(records,bounds,bounds[1:]):
        if not isinstance(r,dict) or type(r.get('start_frame')) is not int or type(r.get('end_frame')) is not int or r['start_frame']!=a or r['end_frame']!=b:
            raise ValueError('Interval type bounds do not match the markers')
        if r.get('type') not in TYPES or r.get('source') not in ('manual','suggested','default'):
            raise ValueError('Invalid interval type')
