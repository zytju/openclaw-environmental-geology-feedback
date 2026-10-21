"""Validate all bindings before generating human-readable views."""
from pathlib import Path
from .contracts import require
from .finalize import context, bound_decision
from .intake import private_output
from .pipeline import save_text, stamp
from .render import feedback_markdown, teacher_markdown


def reading_views(submission, intake, feedback, review, out, decisions=None):
    sub, fb, tr, schemas=context(submission,intake,feedback,review)
    final=bound_decision(sub,fb,tr,schemas,decisions) if decisions else None
    private_output(out,sub)
    out=Path(out)
    require(not out.exists(),'OUTPUT_EXISTS')
    out.mkdir(parents=True,mode=0o700)
    ts=stamp();simulated=sub['material_kind']=='synthetic'
    save_text(out/(sub['student_id']+'.student-reading_'+ts+'.md'),feedback_markdown(fb,simulated,final_record=final,compact=True,submission=sub))
    save_text(out/(sub['student_id']+'.teacher-reading_'+ts+'.md'),teacher_markdown(tr,simulated,feedback=fb,final_record=final,compact=True))
    save_text(out/(sub['student_id']+'.student-evidence_'+ts+'.md'),feedback_markdown(fb,simulated,final_record=final,submission=sub))
    save_text(out/(sub['student_id']+'.teacher-evidence_'+ts+'.md'),teacher_markdown(tr,simulated,feedback=fb,final_record=final))
    return out
