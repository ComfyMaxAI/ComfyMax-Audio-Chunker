"""Explicit phrase splitting and review certification; source evidence is immutable."""
import copy
import hashlib
import json
import math
import uuid


def text_of(phrase):
    return phrase['original_text'] if phrase.get('corrected_text') is None else phrase['corrected_text']


def review_fingerprint(data):
    fields=('id','start','end','original_text','corrected_text','review_status')
    payload=[{k:p.get(k) for k in fields} for p in data['phrases']]
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()


def review_issues(data):
    issues=[]; rate=data['timeline']['sample_rate']; total=data['timeline']['frames']; spans=[]
    for i,p in enumerate(data['phrases'],1):
        if p.get('review_status')!='reviewed': issues.append(f'Phrase {i}: not reviewed')
        a,b=p.get('start'),p.get('end')
        valid=isinstance(a,(int,float)) and isinstance(b,(int,float)) and math.isfinite(a) and math.isfinite(b) and 0<=a<b<=total/rate
        if not valid:
            if text_of(p).strip(): issues.append(f'Phrase {i}: invalid timing')
            continue
        if b-a>15+1e-9: issues.append(f'Phrase {i}: exceeds 15 seconds — split it manually')
        if text_of(p).strip(): spans.append((round(a*rate),round(b*rate)))
    # Overlapping phrases can share a scene, but their indivisible union must fit.
    end=-1; start=0
    for a,b in sorted(spans):
        overlaps=a<end
        if not overlaps: start,end=a,b
        else: end=max(end,b)
        if overlaps and end-start>15*rate:
            issues.append('Overlapping lyric phrases span more than 15 seconds; resolve their timing before review completion')
            break
    return issues


def review_complete(data):
    state=data.get('lyrics_review')
    return isinstance(state,dict) and state.get('fingerprint')==review_fingerprint(data) and not review_issues(data)


def split_state(data,phrase_id,text_index,split_frame):
    """Return a new phrase/history state. Split time is explicitly chosen, not inferred."""
    phrases=copy.deepcopy(data['phrases']); index=next(i for i,p in enumerate(phrases) if p['id']==phrase_id)
    parent=phrases[index]; text=text_of(parent); rate=data['timeline']['sample_rate']; split_time=split_frame/rate
    if type(text_index) is not int or not 0<text_index<len(text) or not text[:text_index].strip() or not text[text_index:].strip():
        raise ValueError('Place the text cursor between two nonempty portions of the corrected lyrics.')
    if type(split_frame) is not int or not parent['start']<split_time<parent['end']:
        raise ValueError('Choose an audio split strictly inside the selected phrase.')
    event_id=str(uuid.uuid4()); children=[]
    for part,(a,b,words) in enumerate(((parent['start'],split_time,text[:text_index]),(split_time,parent['end'],text[text_index:])),1):
        child=copy.deepcopy(parent)
        child.update(id=str(uuid.uuid4()),start=a,end=b,corrected_text=words,review_status='unreviewed',
                     word_alignment_status='phrase_only',split_baseline_text=words,
                     lineage={'parent_id':parent['id'],'root_id':parent.get('lineage',{}).get('root_id',parent['id']),
                              'split_event_id':event_id,'part':part})
        # original_text, imported bounds and source IDs remain complete evidence,
        # not claimed word alignment for either child.
        children.append(child)
    history=copy.deepcopy(data.get('phrase_history',[]))
    history.append(dict(event_id=event_id,parent=parent,child_ids=[p['id'] for p in children],
                        text_index=text_index,split_frame=split_frame,sample_rate=rate))
    phrases[index:index+1]=children
    return dict(phrases=phrases,phrase_history=history,selected_id=children[0]['id'])


def validate_history(data):
    history=data.get('phrase_history',[])
    if not isinstance(history,list): raise ValueError('Invalid phrase split history')
    known={p['id']:p for p in data['phrases']}; events=set()
    for record in history:
        if not isinstance(record,dict) or not isinstance(record.get('parent'),dict): raise ValueError('Invalid archived phrase')
        parent=record['parent']; event=record.get('event_id')
        if not isinstance(event,str) or event in events or not isinstance(parent.get('id'),str) or parent['id'] in known:
            raise ValueError('Duplicate or invalid split lineage')
        events.add(event); known[parent['id']]=parent
    for record in history:
        parent=record['parent']; children=record.get('child_ids'); frame=record.get('split_frame'); rate=record.get('sample_rate')
        if not isinstance(children,list) or len(children)!=2 or len(set(children))!=2 or type(frame) is not int or rate!=data['timeline']['sample_rate']:
            raise ValueError('Invalid split event')
        text=text_of(parent); index=record.get('text_index')
        if type(index) is not int or not 0<index<len(text) or not parent['start']<frame/rate<parent['end']:
            raise ValueError('Invalid split bounds')
        for part,child_id in enumerate(children,1):
            child=known.get(child_id); a,b=(parent['start'],frame/rate) if part==1 else (frame/rate,parent['end'])
            if not child or child.get('lineage',{}).get('split_event_id')!=record['event_id'] or child.get('lineage',{}).get('parent_id')!=parent['id']:
                raise ValueError('Missing phrase lineage')
            if child['start']!=a or child['end']!=b: raise ValueError('Split child bounds changed')
            if child.get('split_baseline_text')!=(text[:index] if part==1 else text[index:]): raise ValueError('Split baseline changed')
            for key in ('original_text','source_word_ids','source_segment_ids','imported_start','imported_end'):
                if child.get(key)!=parent.get(key): raise ValueError('Split source evidence changed')
    for phrase in known.values():
        if 'lineage' in phrase and phrase['lineage'].get('split_event_id') not in events:
            raise ValueError('Missing split history')
