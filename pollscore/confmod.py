from pollscore.period import Period
aliases={}
sessions={}
participation=0
correct=0
_current_session=None

participation_column=None
correctness_column=None
total_column=None
ignore_responses=[]
ignore_roster=[]

def session(timestamp,answerlist=None):
    global _current_session,sessions
    _current_session=Period(timestamp)
    if answerlist is not None:
        sessions[_current_session]=(answerlist,participation,correct)
    else:
        sessions[_current_session]={}

def question(label,answers=None,part=None,corr=None):
    if not _current_session :
        raise RuntimeError("specifying question without session")
    D=sessions[_current_session]
    if not isinstance(D,dict):
        raise RuntimeError("specifying question with an answer list already available")
    if not(answers):
        if corr:
            raise ValueError("No correct answer specified, but score for correct answer nonzero")
        corr = 0
    D[label] = ( (participation if part is None else part), (correct if corr is None else corr),answers)

def exec_config(string):
    exec(string,globals())
