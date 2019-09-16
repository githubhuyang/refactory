import ast
import os
import pandas as pd

#region: Inputs
def get_pyCode(path):
    fnames = [f for f in os.listdir(path) if f.endswith('.py')]
    return [open(path + f).read() for f in fnames] 
    
def get_buggyCorr_codes(path_buggy, path_correct):
    buggyCodes = get_pyCode(path_buggy)
    correctCodes = get_pyCode(path_correct)
    
    print('#BuggyProgs=', len(buggyCodes), '#CorrectProgs=', len(correctCodes))
    return buggyCodes, correctCodes
#endregion

#region: Control Flow (CF)
def get_cf(parse, retLi, cf_single, cf_mult):    
    '''Returns the Control Flow Structure (CF), given an ast parse'''
    if 'body' in parse._fields: # If there exists a 'body'
        for i in parse.body: # For each statement inside body
            className = i.__class__.__name__
            
            if className in cf_mult: # If class is a multi-line CF
                #retLi.append('<' + className + '>')
                retLi.append('(' + className )
                get_cf(i, retLi, cf_single, cf_mult)                
                #retLi.append('</' + className + '>')
                retLi.append(')')
            
            elif className in cf_single: # Else if single statement branching
                #retLi.append('<' + className + '/>')
                retLi.append(className)
                get_cf(i, retLi, cf_single, cf_mult) # For safety, call recur
                
    return retLi

def get_uniqueCfs(codes, cf_single, cf_mult):
    '''Given a list of codes, get Hash frequency list of their CFs'''
    parses = [ast.parse(c) for c in codes]
    cfs = [get_cf(p, [], cf_single, cf_mult) for p in parses]
    
    hashCf = {}
    for cf in cfs:
        cfStr = ' '.join(cf)
        if cfStr not in hashCf:
            hashCf[cfStr] = 0
        hashCf[cfStr] += 1
    
    return hashCf

def get_buggyCorr_cfs(buggyCodes, correctCodes, cf_single, cf_mult):
    buggyCFs = get_uniqueCfs(buggyCodes, cf_single, cf_mult)
    correctCFs = get_uniqueCfs(correctCodes, cf_single, cf_mult)    
    
    print('#BuggyCF=', len(buggyCFs), '#CorrectCF=', len(correctCFs))
    return buggyCFs, correctCFs
#endregion

#region: Analyze CF Hashes
def get_mergeCFs(buggyCFs, correctCFs):
    mergedCFs = []
    for bh in buggyCFs:
        if bh in correctCFs:
            mergedCFs.append((bh, correctCFs[bh], buggyCFs[bh]))
        else:
            mergedCFs.append((bh, 0, buggyCFs[bh]))
            
    for ch in correctCFs:
        if ch not in buggyCFs:
            mergedCFs.append((ch, correctCFs[ch], 0))

    return mergedCFs

def get_dataFrame(buggyCFs, correctCFs, fname_cfs):
    mergedCFs = get_mergeCFs(buggyCFs, correctCFs)

    df_cfs = pd.DataFrame(mergedCFs, columns=['cf', 'numCorrect', 'numWrong'])
    df_cfs = df_cfs.sort_values(['numCorrect', 'numWrong'], ascending=False) # Sort on values
    df_cfs = df_cfs.reset_index(drop=True) # Re-index things
    df_cfs.to_csv(fname_cfs)

    return df_cfs
#endregion

