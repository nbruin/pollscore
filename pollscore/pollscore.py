import pandas as pd
import glob
from pollscore.period import Period
import pollscore.confmod as confmod
from io import StringIO

roster_ID="SIS Login ID"
PointsPossibleID='000-PointsPossible'

class Question:
    r"""Class for storing questions and scoring their responses
    
    Input requires session, label, participation score, correctness score, and
    a set of answers accepted as correct.
    """
    def __init__(self, session, label, particip_score, correct_score, correct_answers):
        self.session=session
        self.label=label
        self.particip_score=particip_score
        self.correct_score=correct_score
        if correct_score>0 and len(correct_answers) == 0:
            raise ValueError("Cannot specify score for correct answer if no correct answers are specified")
        self.correct_answers=correct_answers
    def __repr__(self):
        return "Question {} of {}".format(self.label,self.session)

    def participation_score(self,answer):
        r"""Determines participation score of an answer
        """
        if answer is None or pd.isna(answer) or answer == "":
            return 0
        else:
            return self.particip_score

    def correctness_score(self,answer):
        r"""Determines correctness score of an answer
        """
        if answer in self.correct_answers:
            return self.correct_score
        else:
            return 0

    def total_score(self,answer):
        r"""Determines total score (participation+correctness) of an answer
        """
        if answer is None or pd.isna(answer) or answer == "":
            return 0
        if answer in self.correct_answers:
            return self.particip_score+self.correct_score
        else:
            return self.particip_score
        
class Poll:
    r"""Object to store and analyze poll responses across multiple sessions.
    
    Constructor expects a file name of an appropriately formatted configuration file.
    """
    def __init__(self,config_filename):
        confmod.sessions={}
        confmod.aliases={}
        with open(config_filename) as f:
            config=f.read()
        confmod.exec_config(config)
        #determine the poll report files that need to be considered
        if isinstance(confmod.pollreports,str):
            reportfiles=glob.glob(confmod.pollreports)
        else:
            reportfiles=sum( (glob.glob(f) for f in confmod.pollreports),[])

        domain=confmod.domain
        aliases={ k: v if v.endswith(domain) else v+domain for k,v in confmod.aliases.items()}

        self.reportfiles=reportfiles
        self.rosterfile=confmod.roster
        self.uploadfile=confmod.upload

        self.domain=confmod.domain
        self.aliases=aliases
        self.ignore_responses=set(confmod.ignore_responses)
        self.ignore_roster=set(confmod.ignore_roster)

        self.config_sessions=confmod.sessions
        self._response_tab=None
        self._question_order=None
        self._scorer=None
        self._matches=None
        self._roster=None
        self.rosterfile=confmod.roster
        self._particip_default=confmod.participation
        
        self._participation_column=confmod.participation_column
        self._correctness_column=confmod.correctness_column
        self._total_column=confmod.total_column
 
    def response_table(self):
        r"""Total table of responses.
        
        Rows are indexed by the participant emails. Columns are multi-indexed by session
        (given by a time period) and a poll label. It is an error to have multiple responses
        from a participant to the same question in the same session. Sessions are part of the configuration.
        In addition, the routine here will make up day-long sessions for responses that are not part of a
        configured session. If there are multiple sessions on one day, then this automatic mechanism can lead
        to error reports. The work-around is to configure appropriate sessions. This is usually required anyway for specifying
        answers that are accepted as correct.
        """
        if self._response_tab is not None:
            return self._response_tab
            
        #we collect all poll reports in one dataframe for further analysis
        poll_report=[]
        for f in self.reportfiles:
            #zoom poll reports have two different formats: from 2021 they start with
            #"Poll Report" and then have several introductory lines before the header
            #line for the response table occurs. Before, the header line was the first one.
            #we check for either and then flush all lines up to and including the
            #header line.
            #zoom poll reports have insufficient columns in the header line,
            #which throws off pandas autodetect.
            #other formats would need to be supported here separately.
            with open(f,encoding='utf-8-sig') as handle:
                line = handle.readline()

                #basic format identifier from the first line
                if line != "Poll Report\n" and line != "#,User Name,User Email,Submitted Date/Time,\n":
                    raise RuntimeError("Unrecognized poll report format in file '{}'".format(f))
                #we assume we're looking at a legal poll report. We need to look at a line lower down
                #to further determine the version.
                while not line.startswith("#,User Name,User Email,Submitted Date/Time"):
                    if not line:
                        raise RuntimeError("No poll response header found in file '{}'".format(f))
                    line = handle.readline()

                #split according to versions
                if line == "#,User Name,User Email,Submitted Date/Time,\n":
                    #Pre Sept. 20, 2021 format does not list question number in header, so the header ends with a comma
                    #the responses are (question,answer) pairs.
                    table = pd.read_csv(handle,header=None,usecols=[2,3,4,5],
                            names=["email","time","question","answer"],parse_dates=["time"],
                            na_filter=False)
                else:
                    #Post Sept. 20, 2021 the CSV table actually consists of 1 or more subtables, each with their own
                    #header line with the question in it. We split our input into these subtables
                    #and parse them separately.
                    buffer=[]
                    table=[]
                    question = line[line.rindex(",")+1:-1]
                    while True:
                        line = handle.readline()
                        if line.startswith('#,User Name,User Email,Submitted Date/Time,') or not(line):
                            subtable = pd.read_csv(
                                StringIO(''.join(buffer)),
                                header=None,
                                usecols=[2,3,4],
                                names=["email","time","answer"],
                                parse_dates=["time"],
                                na_filter=False,
                            )
                            buffer = []
                            subtable['question']=question
                            table.append(subtable)
                            if line:
                                question = line[line.rindex(",")+1:-1]
                            else:
                                break #EOF
                        else:
                            buffer.append(line)
                    table = pd.concat(table,ignore_index=True)
                #normalize email case in the event people have used variants
                table.email = table.email.str.lower()
                poll_report.append(table)
        poll_report=pd.concat(poll_report,ignore_index=True)
        self.poll_report=poll_report
        #next: determine sessions. Take sessions from configuration
        sessions=sorted(set(self.config_sessions.keys()))
        if not all(sessions[i]<sessions[i+1] for i in range(len(sessions)-1)):
            raise RuntimeError("Sessions are not disjoint")

        poll_report.set_index(['time'],inplace=True)
        poll_report.sort_index(inplace=True)
        poll_report['session']=None
        for s in sessions:
            poll_report.loc[s.period.start_time:s.period.end_time,'session']=s
            
        while True:
            unassigned = poll_report.loc[poll_report['session'].isnull()]
            if len(unassigned) == 0: break
            s=Period(unassigned.iloc[0].name.date(),"D")
            print("Found response outside session. Creating {}.".format(s))
            sessions.append(s)
            sessions.sort()
            if not all(sessions[i]<sessions[i+1] for i in range(len(sessions)-1)):
                raise RuntimeError("Sessions are not disjoint")
            poll_report.loc[s.period.start_time:s.period.end_time,'session']=s
           
        poll_report.reset_index(inplace=True)

        all_questions=poll_report.groupby(["session","question"])
        questions_startstop=pd.DataFrame(
            {"min":all_questions['time'].min().rename("min"),
             "max":all_questions['time'].max().rename("max")})
        question_periods=questions_startstop.apply(lambda a: Period(*a),axis=1)
        question_order={s: list(q.sort_values().reset_index()['question']) for s,q in question_periods.groupby("session")}
        try:
            response_table=[ql.set_index(["session","question","email"])['answer'].unstack('session').unstack("question") for s, ql in poll_report.groupby(["session"])]
        except ValueError as E:
            raise ValueError("Probably multiple responses with same participant, session, and question.") from E
        response_table=pd.concat(response_table,axis=1,join='outer',sort=True)
        response_table.index.rename('email',inplace=True)
        index=[]
        for s in list(sessions):
            if s in question_order:
                for q in question_order[s]:
                    index.append((s,q))
            else:
                print("Dropping session {} because it registered no responses.".format(s))
                sessions.remove(s)
        response_table=response_table[index]
        
        self.sessions=sessions
        self._question_order=question_order
        self._response_tab=response_table
        return self._response_tab

    def question_order(self):
        r"""Returns a dictionary with sessions as keys and as values the list of questions chronologically ordered by responses
        """
        if self._question_order is None:
            self.response_table()
        return self._question_order

    def match(self):
        r"""Match participant emails with roster entries
        
        returns answer as a dictionary with entries <email>:<roster ID>
        """
        if self._matches is not None:
            return self._matches
        roster=pd.read_csv(self.rosterfile,dtype=str)
        I = next(i for i,n in enumerate(roster["Student"]) if isinstance(n,str) and n.strip() == "Points Possible")
        roster=roster.drop(range(I+1))
        roster_ids=set(roster[roster_ID])
        domain_emails={id+self.domain for id in roster_ids if id not in self.ignore_roster}
        strip=-len(self.domain)
        def match(email):
            if email in self.ignore_responses:
                return ''
            email = self.aliases.get(email) or email
            if email.lower() in domain_emails:
                return email[:strip].lower()
            else:
                return ''
        emails=set(self.response_table().index)
        matches={email:match(email) for email in self.response_table().index}
        matches={e:id for e,id in matches.items() if id}
        
        unmatched_emails=emails.difference(matches.keys()).difference(self.ignore_responses)
        unmatched_ids=roster_ids.difference(matches.values()).difference(self.ignore_roster)

        if len(unmatched_emails) == 1:
            print("Found 1 unmatched email in responses: {}".format(next(iter(unmatched_emails))))
        elif len(unmatched_emails) > 1:
                print("Found {} unmatched emails in responses: {}".format(len(unmatched_emails),sorted(unmatched_emails)))

        if len(unmatched_ids) == 1:
            print("Found 1 roster id without matched responses: {}".format(next(iter(unmatched_ids))))
        elif len(unmatched_ids) > 1:
            print("Found {} roster ids without matched responses: {}".format(len(unmatched_ids),sorted(unmatched_ids)))
        self._roster=roster
        self._matches=matches
        return matches
        
    def fullroster(self):
        r"""full roster table as read in from the relevant csv"""
        if self._roster is None:
            self.matches()
        return self._roster
        
    def scorers(self):
        r"""returns dictionary of scorers for the poll questions
        """
        if self._scorer is not None:
            return self._scorer
        scorer={}
        question_order=self.question_order()
        for s in self.sessions:
            d=self.config_sessions.get(s,{})
            if isinstance(d,tuple):
                answers=d[0].split(',')
                question_labels=question_order[s]
                if len(answers) > len(question_labels):
                    print("Session {} has more correct answers specified than questions. Only using first {} answers specified.".
                        format(s,len(question_labels)))
                    answers=answers[:len(question_labels)]
                scorer.update({(s,l):Question(s,l,d[1],d[2] if a else 0,set(a)) for l,a in zip(question_labels,answers)})
                if len(answers) < len(question_labels):
                    print("Session {} has insufficient answers specified. Scoring last {} only for participation.".format(s,len(question_labels)-len(answers)))
                    scorer.update({(s,l):Question(s,l,d[1],0,set()) for l in question_labels[len(answers):]})
            if isinstance(d,dict):
                with_answers=set(d.keys())
                with_responses=set(question_order[s])
                no_responses=with_answers.difference(with_responses)
                no_answers=with_responses.difference(with_answers)
                if len(no_responses) > 0:
                    print("Session {} questions without responses, but scoring specified: {}.".format(s,no_responses))
                if len(no_answers) > 0:
                    print("Session {} questions {} have responses but no scoring. Scoring {} points for participation only.".format(s,sorted(no_answers),self._particip_default))
                for l in question_order[s]:
                    if l in no_answers:
                        particip_score, correct_score, answers=(self._particip_default, 0, set())
                    else:
                        particip_score, correct_score, answers = d[l]
                        if answers is None:
                            answers={}
                        elif isinstance(answers,str):
                            answers={answers}
                    scorer[(s,l)]=Question(s,l,particip_score,correct_score,answers)
        self._scorer=scorer
        return scorer
        
    def participation_table(self):
        r"""produce a table with rows indexed by partipant emails and columns all the poll questions. Values are participation scores"""
        responses=self.response_table()
        scorers=self.scorers()
        return pd.DataFrame({l:responses[l].map(s.participation_score) for l,s in scorers.items()})

    def correctness_table(self):
        r"""produce a table with rows indexed by partipant emails and columns all the poll questions. Values are correctness scores"""
        responses=self.response_table()
        scorers=self.scorers()
        return pd.DataFrame({l:responses[l].map(s.correctness_score) for l,s in scorers.items()})

    def totals_table(self):
        r"""produce a table with rows indexed by partipant emails and columns all the poll questions. Values are total scores"""
        responses=self.response_table()
        scorers=self.scorers()
        return pd.DataFrame({l:responses[l].map(s.total_score) for l,s in scorers.items()})
        
    def matched_roster(self):
        r"""produce a table representing the matched entries from the roster. Also includes a "points possible" row."""
        match=self.match()
        roster=self.fullroster()
        matchroster=roster[roster[roster_ID].isin(match.values())].set_index(roster_ID)
        matchroster.loc[PointsPossibleID]=("   Points Possible",'','','')
        matchroster.sort_index(inplace=True)
        return matchroster
        
    def roster_table(self):
        r"""produce a score table in roster format. This is a roster table with some/all columns for participation, correctness, and total score.
        
        The points possible row is filled in with the max score for the relevant column. Configuration
        determines which columns are included and with which label.
        """
        matchdict=self.match()
        matchroster=self.matched_roster()
        columns_to_add=[]
        if self._participation_column:
            scores=self.participation_table().sum(axis=1).rename(self._participation_column).reset_index()
            scores[roster_ID]=scores['email'].map(matchdict.get)
            scores=scores[~scores[roster_ID].isnull()].drop("email",axis=1).set_index(roster_ID)
            max_score=sum(s.particip_score for s in self.scorers().values())
            scores.loc[PointsPossibleID]=max_score
            columns_to_add.append(scores)
        if self._correctness_column:
            scores=self.correctness_table().sum(axis=1).rename(self._correctness_column).reset_index()
            scores[roster_ID]=scores['email'].map(matchdict.get)
            scores=scores[~scores[roster_ID].isnull()].drop("email",axis=1).set_index(roster_ID)
            max_score=sum(s.correct_score for s in self.scorers().values())
            scores.loc[PointsPossibleID]=max_score
            columns_to_add.append(scores)
        if self._total_column:
            scores=self.totals_table().sum(axis=1).rename(self._total_column).reset_index()
            scores[roster_ID]=scores['email'].map(matchdict.get)
            scores=scores[~scores[roster_ID].isnull()].drop("email",axis=1).set_index(roster_ID)
            max_score=sum(s.particip_score +s.correct_score for s in self.scorers().values())
            scores.loc[PointsPossibleID]=max_score
            columns_to_add.append(scores)
        W=matchroster.join(columns_to_add).reset_index()
        W.at[0,roster_ID]=''
        cols=list(self.fullroster().columns) + [c.columns[0] for c in columns_to_add]
        return W[cols].sort_values(cols[0])
        
    def write_submission(self):
        r"""write csv file of the roster table, suitable for upload in CMS.
        """
        W=self.roster_table()
        with open(self.uploadfile,"w") as f:
            f.write(W.to_csv(index=False))
            
def main(*args):
    import argparse

    parser = argparse.ArgumentParser(description="Score Zoom poll reports for upload to a course management system.")
    parser.add_argument("files", metavar="FILE", type=str, nargs='*',
        help = "if specified, process given report files instead of configured ones.")
    parser.add_argument("-c","--config", type=str, default='config', help = "config file (default 'config')")
    args = parser.parse_args()

    print("args:",args)
    print("-----------\nPOLL SCORE PROCESSING\n-----------");
    print('Processing poll configuration from file "{}"'.format(args.config))
    P = Poll(args.config)
    if args.files:
        print("Report files overridden by command line argument. Working with: {}".format(args.files))
        P.reportfiles = args.files
    else:
        print("Configured report files: {}".format(P.reportfiles))
    print("Configured sessions: {}".format(sorted(P.config_sessions.keys())))
    print("-----------\nRESPONSE PROCESSING\n-----------");
    P.response_table()
    print("-----------\nSCORING PROCESSING\n-----------");
    P.scorers()
    print("-----------\nMATCHING ROSTER\n-----------");
    P.matched_roster()
    print("-----------\nWRITING SCORE FILE\n-----------");
    P.write_submission()
    maxscores = P.roster_table().iloc[0]
    for col in [P._participation_column, P._correctness_column, P._total_column]:
        if col:
            print("Maximum {}: {}".format(col,maxscores[col]))
    print("Report in {} is ready for upload".format(P.uploadfile))
    

if __name__ == "__main__":
    main()
