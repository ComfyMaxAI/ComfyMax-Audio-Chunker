"""Scene proposals in integer audio frames; never writes phrases or regions."""
import math
from .lyrics_workflow import review_complete,review_issues


def lyrics(phrase):
    text=phrase.get('corrected_text')
    return phrase.get('original_text','') if text is None else text


def phrase_spans(data):
    rate=data['timeline']['sample_rate']; total=data['timeline']['frames']
    return [(round(p['start']*rate),round(p['end']*rate),p) for p in data['phrases']
            if lyrics(p).strip() and isinstance(p.get('start'),(int,float))
            and isinstance(p.get('end'),(int,float)) and 0<=p['start']<p['end']<=total/rate]


def validate_cuts(cuts,total):
    if not isinstance(cuts,list) or any(type(c) is not int or not 0<c<total for c in cuts):
        raise ValueError('Scene cuts must be integer sample positions inside the song')
    if cuts!=sorted(set(cuts)):
        raise ValueError('Scene cuts must be unique and increasing')


def activity_blocks(data,analysis):
    rate=data['timeline']['sample_rate']; total=data['timeline']['frames']
    spans=[(a,b) for a,b,p in phrase_spans(data)]
    spans += [(max(0,round(r['start']*rate)),min(total,round(r['end']*rate)))
              for r in analysis.get('regions',[]) if r['kind']=='vocal']
    merged=[]
    for a,b in sorted(spans):
        if b<=a: continue
        # Brief breaths/detector dropouts are not mandatory separate scenes.
        if merged and a-merged[-1][1]<3*rate: merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
        else: merged.append((a,b))
    return merged


def propose(data,analysis):
    if not review_complete(data):
        raise ValueError('Complete Lyrics Review before generating scenes.\n'+'\n'.join(review_issues(data)[:8]))
    rate=data['timeline']['sample_rate']; total=data['timeline']['frames']
    phrases=phrase_spans(data); result=[0]
    def instrumental(a,b):
        if b<=a: return
        count=max(1,round((b-a)/rate/5.5))
        result.extend(a+round((b-a)*i/count) for i in range(1,count+1))
    def vocal(a,b):
        # Reviewed phrases are indivisible: candidates inside any phrase are
        # removed entirely. No duration target may override that invariant.
        natural={a,b}
        for start,end,p in phrases:
            natural.update(t for t in (start,end) if a<t<b)
        transitions={round(r[k]*rate) for r in analysis.get('regions',[]) for k in ('start','end')
                     if a<round(r[k]*rate)<b}
        candidates=sorted(t for t in natural|transitions|set(range(a,b,max(1,round(rate*.5))))
                          if not any(start<t<stop for start,stop,p in phrases))
        cost=[float('inf')]*len(candidates); prev=[-1]*len(candidates); cost[0]=0
        for j in range(1,len(candidates)):
            end=candidates[j]
            boundary=0 if end in natural else (1 if end in transitions else 12)
            for i in range(j-1,-1,-1):
                duration=(end-candidates[i])/rate
                if duration>15: break
                short=100*(5-duration)**2 if duration<5 else 0
                value=cost[i]+5+((duration-10)/3)**2+short+boundary
                if value<cost[j]: cost[j]=value; prev[j]=i
        j=len(candidates)-1; path=[]
        if not math.isfinite(cost[j]):
            raise ValueError('These reviewed phrase timings cannot form scenes of at most 15 seconds without splitting a phrase. Return to Lyrics and resolve the timing.')
        while j>0:
            path.append(candidates[j]); j=prev[j]
            if j<0: raise ValueError('Cannot construct a valid scene proposal')
        result.extend(reversed(path))
    position=0
    for a,b in activity_blocks(data,analysis):
        instrumental(position,a); vocal(a,b); position=b
    instrumental(position,total)
    cuts=sorted(set(result)-{0,total}); validate_cuts(cuts,total)
    return cuts


def scene_rows(data,analysis):
    rate=data['timeline']['sample_rate']; total=data['timeline']['frames']
    cuts=data.get('chunk_boundaries',[]); validate_cuts(cuts,total)
    bounds=[0]+cuts+[total]; phrases=phrase_spans(data); rows=[]
    for i,(a,b) in enumerate(zip(bounds,bounds[1:])):
        related=[p for start,end,p in phrases if start<b and end>a]
        vocal=bool(related) or any(r['kind']=='vocal' and round(r['start']*rate)<b and round(r['end']*rate)>a for r in analysis.get('regions',[]))
        warnings=[]
        if b-a>15*rate: warnings.append('OVER 15 SECONDS')
        if b-a<5*rate: warnings.append('Under 5 seconds')
        if any(start<t<end for start,end,p in phrases for t in (a,b)):
            warnings.append('Cut inside a timed phrase — audition required')
        text='\n'.join(lyrics(p).strip() for p in related)
        rows.append(dict(scene=i+1,start_frame=a,end_frame=b,start=a/rate,end=b/rate,duration=(b-a)/rate,
                         lyrics=text or ('Vocal — no transcript' if vocal else 'Instrumental'),
                         phrase_ids=[p['id'] for p in related],warnings=warnings))
    return rows
