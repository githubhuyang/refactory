from . import rule, ruleMatcher, controlFlow, Helper as H
import ast, os, csv, astunparse

#region: Global Params
question = 'question_104019'
verboseFnames = ['test2.py'] #  'sub_6367849.py', 'sub_6367433.py', 'sub_6372899.py']
verboseRnames = ['D3.x']

testFile = './data/minimal_dataset/online/question_103853/code/correct/sub_6394872.py'
#endregion

#region: Global Consts
path_data = './data/manual/'
path_q = path_data + question + '/'

path_correct = path_q + 'code/correct/'
path_buggy = path_q + 'code/wrong/'
fname_cfs = path_q + 'controlFlows.csv'

fname_summaryR = path_q + 'summary_perRule.csv'
fname_summaryC = path_q + 'summary_perCode.csv'
fname_refactor = path_q + 'refactor.csv'

cf_single = ['Return', 'Continue', 'Break', 'Call', 'Import', 'ImportFrom', 'Lambda', 'Yield']
cf_mult = ['FunctionDef', 'For', 'If', 'ClassDef', 'While', 'ListComp', 'Module']
#endregion

#region: Main for controlFlows
def main_controlFlow():
    buggyCodes, correctCodes = controlFlow.get_buggyCorr_codes(path_buggy, path_correct)
    buggyCFs, correctCFs = controlFlow.get_buggyCorr_cfs(buggyCodes, correctCodes, cf_single, cf_mult)
    df_cfs = controlFlow.get_dataFrame(buggyCFs, correctCFs, fname_cfs)
#endregion

#region: Main for AST transformations
class Refactor:
    def __init__(self, fname, origCode, depth=1):
        self.fname = fname
        self.origCode = origCode
        self.ruleAppls = {} # {rule-id: [newCode1, newCode2]}
        self.depth = depth # How many far away (#rule-applications) is it from code in fname?
    
    def addRuleAppl(self, r, replNodes):
        self.ruleAppls[r.name] = [astunparse.unparse(n) for n in replNodes]

    def __str__(self):
        stri = 'OrigCode:\n' + self.origCode + 'RuleAppls:\n'
        for ruleName in self.ruleAppls:
            stri += '-'*3 + ruleName + '-'*3 + ': #'+ str(len(self.ruleAppls[ruleName])) +'\n' 
            for refactoredCode in self.ruleAppls[ruleName]:
                stri += refactoredCode + '\n\n'

        return stri

def writeResults(results):
    li_summC, li_indiv = [], []
    rnames = [rname for rname in sorted([r.name for r in rule.rules])]
    headers = ['file_name', 'rule_name', 'depth', 'before_refactor', 'after_refactor']
    di_summR = {rname:0 for rname in rnames}

    for res in results:
        summC = []
        
        for rname in sorted(res.ruleAppls):
            di_summR[rname] += len(res.ruleAppls[rname])
            if len(res.ruleAppls[rname]) > 0:
                summC += [len(res.ruleAppls[rname])]
            else:
                summC.append(None)

            for newCode in res.ruleAppls[rname]:
                li_indiv += [[res.fname, rname, res.depth, res.origCode, newCode]]

        li_summC += [[res.fname] + summC]        

    print('Total Rule applications=', sum(di_summR.values()))
    print(di_summR)

    H.writeCSV(fname_summaryC, ['fname'] + rnames, li_summC)
    H.writeCSV(fname_summaryR, ['rule-name', '#matches'], di_summR.items())
    H.writeCSV(fname_refactor, headers, li_indiv)

def applyRules(refactor:Refactor, untilDepth, results, currDepth=1):
    '''Repeatedly apply rules on refactor object, upto a specified depth'''
    #print(refactor.fname, currDepth)
    for r in rule.rules:
        corrParse = ast.parse(refactor.origCode) # Run parse for each rule, since original parse modified!
        verbose =  (r.name in verboseRnames) and (refactor.fname in verboseFnames) 
        if verbose:
            print('-'*50, '\nDebugging fname='+ refactor.fname, 'rname='+r.name, '\n'+'-'*50)               
        else:
            pass
        tree, nodeO, replNodes = ruleMatcher.matchOrig(corrParse, r, verbose=verbose)
        refactor.addRuleAppl(r, replNodes)
        
    if 'test' not in refactor.fname:
        results.append(refactor)

    if untilDepth != currDepth: # Depth not exhausted
        applyRules_rec(refactor, untilDepth, results, currDepth=currDepth) # Apply on all newly generated

    return results

def applyRules_rec(refactor:Refactor, untilDepth, results, currDepth=1):
    for index in range(len(results)): # For each result
        refactor = results[index]

        if refactor.depth == currDepth: # that was newly generated in current run
            for rname in refactor.ruleAppls: # For each rule
                for newCode in refactor.ruleAppls[rname]: # For each new code
                    newRefactor = Refactor(refactor.fname, newCode, depth=refactor.depth+1) # 
                    applyRules(newRefactor, untilDepth=untilDepth, results=results, currDepth=currDepth+1)

def main_astMatcher():
    '''For each correct program: apply rules and record transformation'''
    fnames = [f for f in os.listdir(path_correct) if f.endswith('.py')]
    results = []

    for fname in sorted(fnames):
        corrCode = open(path_correct+fname).read()
        refactor = Refactor(fname, corrCode)        
        results += applyRules(refactor, untilDepth=1, results=[])
    
    print('Wrote results for #correct=', len(fnames), 'and #rules=', len(rule.rules))
    writeResults(results)