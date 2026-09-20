"""Authoritative manual markers and explicit scene snapshots. No lyric dependency."""
import copy
from fractions import Fraction
from .interval_types import TYPES,reconcile,validate_interval_types


def validate_positions(markers,total):
    if not isinstance(markers,list) or any(type(m) is not int or not 0<m<total for m in markers):
        raise ValueError('Markers must be sample positions inside the song. Start and end are fixed.')
    if markers!=sorted(set(markers)):
        raise ValueError('Markers must be unique and increasing.')


def validate_marker_state(state,total):
    if not isinstance(state,dict): raise ValueError('Invalid marker project data')
    validate_positions(state.get('markers'),total)
    if 'interval_types' in state: validate_interval_types(state['interval_types'],boundaries(state,total))
    snapshot=state.get('scenes')
    if snapshot is not None:
        if not isinstance(snapshot,dict): raise ValueError('Invalid created scenes')
        bounds=snapshot.get('boundaries')
        if not isinstance(bounds,list) or len(bounds)<2 or any(type(b) is not int for b in bounds) or bounds[0]!=0 or bounds[-1]!=total:
            raise ValueError('Created scenes must cover the whole song.')
        validate_positions(bounds[1:-1],total)
        if 'types' in snapshot and (not isinstance(snapshot['types'],list) or len(snapshot['types'])!=len(bounds)-1 or any(t not in TYPES for t in snapshot['types'])):
            raise ValueError('Invalid scene types')


def initial_state(data,classifier=None):
    """Copy prior cuts once as manual markers; never certify old proposals."""
    state=copy.deepcopy(data.get('marker_editor',dict(markers=list(data.get('chunk_boundaries',[])),scenes=None)))
    validate_marker_state(state,data['timeline']['frames'])
    ensure_types(state,data['timeline']['frames'],classifier)
    if state.get('scenes') and 'types' not in state['scenes']:
        state['scenes']['types']=[r['type'] for r in reconcile(state['interval_types'],state['scenes']['boundaries'],classifier)]
    return state


def ensure_types(state,total,classifier=None):
    if 'interval_types' not in state:
        state['interval_types']=reconcile([],boundaries(state,total),classifier)


def set_interval_type(state,index,value,total):
    if value not in TYPES or type(index) is not int or not 0<=index<len(state['markers'])+1:
        raise ValueError('Choose Vocal or Instrumental for an interval, not the final song-end boundary.')
    result=copy.deepcopy(state); ensure_types(result,total)
    result['interval_types'][index]['type']=value; result['interval_types'][index]['source']='manual'
    return result


def boundaries(state,total):
    return [0]+state['markers']+[total]


def intervals(bounds,rate):
    return [dict(scene=i+1,start_frame=a,end_frame=b,start=a/rate,end=b/rate,
                 duration=(b-a)/rate,over_limit=b-a>15*rate)
            for i,(a,b) in enumerate(zip(bounds,bounds[1:]))]


def created_scenes(state,rate):
    if not state.get('scenes'): return []
    rows=intervals(state['scenes']['boundaries'],rate)
    for row,kind in zip(rows,state['scenes'].get('types',['Vocal']*len(rows))): row['type']=kind
    return rows


def scenes_current(state,total):
    return bool(state.get('scenes') and state['scenes']['boundaries']==boundaries(state,total) and
                state['scenes'].get('types')==[r['type'] for r in state.get('interval_types',[])])


def create_scenes(state,total):
    result=copy.deepcopy(state)
    ensure_types(result,total)
    result['scenes']={'boundaries':boundaries(result,total),'types':[r['type'] for r in result['interval_types']]}
    return result


def add_marker(state,frame,total,classifier=None):
    result=copy.deepcopy(state); result['markers']=sorted(state['markers']+[frame])
    validate_positions(result['markers'],total)
    result['interval_types']=reconcile(state.get('interval_types',[]),boundaries(result,total),classifier)
    validate_marker_state(result,total); return result


def move_marker(state,old,new,total,classifier=None):
    if old not in state['markers']: raise ValueError('Select an interior marker to move.')
    result=copy.deepcopy(state); result['markers'].remove(old); result['markers'].append(new); result['markers'].sort()
    validate_positions(result['markers'],total)
    result['interval_types']=reconcile(state.get('interval_types',[]),boundaries(result,total),classifier)
    validate_marker_state(result,total); return result


def delete_marker(state,frame,total,classifier=None):
    if frame not in state['markers']: raise ValueError('Song start and end cannot be deleted.')
    result=copy.deepcopy(state); result['markers'].remove(frame)
    result['interval_types']=reconcile(state.get('interval_types',[]),boundaries(result,total),classifier)
    return result


def add_automatic_markers(state,total,rate,seconds=15.0,clear_existing=True):
    """Place sample-rounded absolute intervals; start/end remain fixed boundaries."""
    if type(total) is not int or total<=0 or type(rate) is not int or rate<=0:
        raise ValueError('The master song must have a valid duration and sample rate.')
    try:
        step=Fraction(str(seconds))*rate
    except (ValueError,ZeroDivisionError):
        raise ValueError('Choose a finite positive interval in seconds.') from None
    if step<1:
        raise ValueError('The interval must be at least one audio sample.')
    # Round each absolute position, not a rounded step, to avoid cumulative drift.
    count=(total*step.denominator+step.numerator-1)//step.numerator
    generated={round(i*step) for i in range(1,count)}
    result=copy.deepcopy(state)
    result['markers']=sorted({p for p in generated if 0<p<total} |
                             (set() if clear_existing else set(state['markers'])))
    # No activity classifier: fresh intervals use the existing Vocal default.
    result['interval_types']=reconcile([] if clear_existing else state.get('interval_types',[]),
                                       boundaries(result,total))
    validate_marker_state(result,total)
    return result
