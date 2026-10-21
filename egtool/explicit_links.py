"""Normalize only issue IDs explicitly named by the model; retain original output."""
import copy,re
from .contracts import digest

def normalize_explicit_links(feedback):
    out=copy.deepcopy(feedback);known={i['issue_id'] for d in feedback['dimensions'] for i in d['issues']};changes=[]
    for d in out['dimensions']:
        if d['assessment']!='partial' or d['issues'] or d.get('related_issue_ids'):continue
        ids=list(dict.fromkeys(re.findall(r'(?<![A-Za-z0-9])I[0-9]{2,6}(?![0-9])',d['basis'])))
        if ids and set(ids)<=known:
            d['related_issue_ids']=ids;changes.append({'dimension':d['dimension'],'related_issue_ids':ids,'source_field':'basis'})
    record={'kind':'explicit_issue_link_normalization','original_feedback_sha256':digest(feedback),
            'normalized_feedback_sha256':digest(out),'changes':changes,
            'assessment_and_text_changed':False,'teacher_approval_created':False}
    return out,record
