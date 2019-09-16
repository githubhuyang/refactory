import ast, copy

import os
import pandas as pd
from basic_framework.refactoring_ast import ruleAction

jump_instr = [ast.Return, ast.Continue, ast.Break, ast.Raise, ast.Yield, ast.YieldFrom]
block_instr = [ast.ClassDef, ast.Lambda, ast.ListComp, ast.Try, ast.While, ast.With, ast.For, ast.FunctionDef, ast.If]

#region: Match
class Match:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.delNodes = [] # Nodes to delete, in original tree
        self.replHash = {} # Named nodes to replace, in original tree
        
        # Overall success;
        self.success = None # None=>Unknown, True=>Matching complete, False=>Matching failed
        # Waiting for block completion? If greedy (BLOCK-tag), one name (in replHash) can consume multiple node elements of list
        self.blockFlag = None # None=>Unknown, True=>Waiting for end of block, False=>block completed
        # Waiting for jump instruction? (when encounter JUMP-tag). Match success incomplete if this is True
        self.jumpFlag = None # None=>Unknown, True=>Waiting for jump, False=>Matching complete
        # Waiting for return instruction? (when encounter RETURN-tag). Match success incomplete if this is True
        self.returnFlag = None # None=>Unknown, True=>Waiting for return, False=>Matching complete
        # Waiting for Break instruction? (when encounter BREAK-tag). Match success incomplete if this is True
        self.breakFlag = None # None=>Unknown, True=>Waiting for break, False=>Matching complete

#endregion

#region: Matcher
class Matcher:
    '''Contains a list of Match objects'''
    def __init__(self):
        self.matches = [Match()]

    def reset(self, recLevel):
        if recLevel == 1:
            self.matches[-1].reset()

    def setBlock(self, nodeO):
        prevMatch = self.matches[-1]                

        if prevMatch.blockFlag is None: # If block creation yet to start
            prevMatch.blockFlag = True # Set to await status
        else: # Else, block addition ongoing/already-ended
            pass # Do nothing

        return True

    def checkNextBlock(self, childrenO, index):
        '''Check if there is a block change'''
        if index+1 < len(childrenO):
            nodeO = childrenO[index+1]
            prevMatch = self.matches[-1]  

            # Change block at Control-Flow change/encountering Jump-Instruction
            # if type(nodeO) in block_instr + jump_instr: # Check if change in block 
            #     prevMatch.blockFlag = False # End block progression
                # Irrespective of whether block was already in progress, or yet to start

    def getBlock(self):
        return self.matches[-1].blockFlag 

    def setJump(self, nodeO):
        prevMatch = self.matches[-1]
        if type(nodeO) in jump_instr: # Check if jump instruction found
            prevMatch.jumpFlag = False # If found, set jump await flag to "False"
        elif prevMatch.jumpFlag is None: # Else if jump instruction not found earlier
            prevMatch.jumpFlag = True # Set to await status
        else: # Else, jump instruction has been found earlier
            pass # Do nothing
    
    def setReturn(self, nodeO):
        prevMatch = self.matches[-1]
        if type(nodeO) == ast.Return: # Check if return instruction found
            prevMatch.returnFlag = False # If found, set return await flag to "False"
        elif prevMatch.returnFlag is None: # Else if return instruction not found earlier
            prevMatch.returnFlag = True # Set to await status
        else: # Else, return instruction has been found earlier
            pass # Do nothing

    def setBreak(self, nodeO):
        prevMatch = self.matches[-1]
        if type(nodeO) == ast.Break: # Check if break instruction found
            prevMatch.breakFlag = False # If found, set break await flag to "False"
            return False
        elif prevMatch.breakFlag is None: # Else if break instruction not found earlier
            prevMatch.breakFlag = True # Set to await status            
        else: # Else, break instruction has been found earlier
            pass # Do nothing

        return True

    def addRepl(self, name, value):
        replHash = self.matches[-1].replHash
        if name in replHash: # If already exists
            if type(replHash[name]) is not list: 
                replHash[name] = [replHash[name]] # Make it a list
            replHash[name].append(value) # And add new value in the end
        else:
            replHash[name] = value # Else, set the name-value pair

    def add(self, tempSuccess, recLevel, delNodes):
        '''Check and add successful match'''
        prevMatch = self.matches[-1]
        prevMatch.blockFlag = None # Switch off greedy flag at end of list

        # When not waiting for jump instr, and only at base recursion level success
        if not prevMatch.jumpFlag and not prevMatch.returnFlag and not prevMatch.breakFlag \
            and tempSuccess and recLevel==1: 
            prevMatch.delNodes = delNodes # Add delNodes
            prevMatch.success = True # Set success
            self.matches.append(Match()) # and create new match object

#endregion

# region: Helper funcs
def pprint(verbose, recLevel, funcName, nodeR, nodeO):
    if verbose:
        print('  '*recLevel, 'matchRule.'+funcName+':', 'nodeR=',nodeR, 'nodeO=', nodeO)

def get_children(nodeO, nodeR):
    '''If nodeR is list and nodeO is list-like (list/node with body)'''
    if type(nodeR) is list:
        if type(nodeO) is list:
            return nodeO, nodeR
        elif hasattr(nodeO, 'body') and len(nodeR) <= len(nodeO.body): 
            return nodeO.body, nodeR # Orig list has at least as many nodes as Rule list
    
    return None, None

#endregion

#region: Match NodeR-NodeO pair recursively

def matchRule_name(nodeO, nodeR, matcher, recLevel=1, verbose=False):
    '''If nodeO exists and nodeR is Name (or named Expression), create hash and return'''
    name = None
    if nodeO and type(nodeR) is ast.Name:        
        name = nodeR.id
    elif nodeO and type(nodeR) is ast.Expr and type(nodeR.value) is ast.Name:     
        name = nodeR.value.id
        
    if name:                       
        appendToBlock = True 
        if 'JUMP' in name: # If waiting for JUMP match
            matcher.setJump(nodeO)
        
        if 'RETURN' in name: # If waiting for RETURN match
            matcher.setReturn(nodeO)

        if 'BREAK' in name: # If waiting for BREAK match
            appendToBlock = matcher.setBreak(nodeO) # Don't append successful break matches

        if 'BLOCK' in name: # If block match
            matcher.setBlock(nodeO) # set matcher to be greedy            

        if appendToBlock:
            matcher.addRepl(name, nodeO)        
        pprint(verbose, recLevel, 'name', name, nodeO)
        return True
    

# def matchRule_expr(nodeO, nodeR, matches, recLevel=1, verbose=False):
#     '''If (incorrectly) parsed as expression, recurse with nodeR=value, nodeO=same. That is, match Expr with list.'''  
#     if nodeO and type(nodeR) is list and len(nodeR)==1 and type(nodeR[0]) is ast.Expr:        
#         return True

def matchRule_list(nodeO, nodeR, matcher, recLevel=1, verbose=False):
    '''If list, search for multiple consecutive children'''
    # Is nodeR a list?
    childrenO, childrenR = get_children(nodeO, nodeR)
    if childrenO is not None and childrenR is not None: 

        # Init default success
        pprint(verbose, recLevel, 'list-...', nodeR, nodeO) 
        success = (len(nodeR) == 0 and len(nodeO) == 0) # If empty lists, nothing to match. Else false        
        numCombinations = len(childrenO) - len(childrenR) + 1 # Try as many as oCr combinations
        if recLevel != 1: # Unless not at base level
            numCombinations = 1 # Then, match sequentially, beginning to end

        # Pairwise match
        for initI in range(numCombinations): # Try all consecutive combinations of Orig list
            indexR, indexO, tempSuccess, delNodes = 0, 0, False, []

            while indexR < len(childrenR) and initI+indexO < len(childrenO): # For each orig-rule elementwise pair 
                childO, childR = childrenO[initI + indexO], childrenR[indexR]                
                tempSuccess = matchRule(childO, childR, matcher, recLevel=recLevel+1, verbose=verbose)
                delNodes.append(childO)
                
                if not tempSuccess: # failed childO-childR match
                    matcher.reset(recLevel) # reset and try next zip (consecutive combination)
                    break
                
                # Check for block change in next node (to decide on indexR increment)
                matcher.checkNextBlock(childrenO, initI+indexO)
                indexO += 1 # Increment indices
                if not matcher.getBlock(): # If greedy switch on, don't increment indexR
                    indexR += 1

            # If found successful match
            success = success or tempSuccess  # found at least one pair of success
            matcher.add(tempSuccess, recLevel, delNodes)

        pprint(verbose, recLevel, 'list-'+str(success), nodeR, nodeO)     
        return success

def matchRule_type(nodeO, nodeR, matcher, recLevel=1, verbose=False):
    '''# otherwise, match the type (and its corresponding fields) directly'''
    if type(nodeR) is not list and type(nodeR) == type(nodeO): # If not list, and same type
        pprint(verbose, recLevel, 'type-...', nodeR, nodeO)   

        if hasattr(nodeO, '_fields'): # Match all fields
            for field in nodeO._fields: # Field names are same, since nodeO and nodeR are same type

                pprint(verbose, recLevel+1, 'field='+field, getattr(nodeR, field), getattr(nodeO, field))           
                success = matchRule(getattr(nodeO, field), getattr(nodeR, field), matcher, recLevel=recLevel+1, verbose=verbose)
                if not success: # failed hash
                    pprint(verbose, recLevel, 'type-false', nodeR, nodeO)   
                    return False

        pprint(verbose, recLevel, 'type-true', nodeR, nodeO)   
        return True

#region: match nodeR recursively
def matchRule(nodeO, nodeR, matcher, recLevel=1, verbose=False):
    '''Given a original-node and rule-node, recursively match until failure.
That is, don't recurse the original node on failure.
Each recursion step goes within rule.match on success.
recLevel => recursion level of matchRule func.'''
    
    # If nodeO exists and nodeR is Name, create hash and return
    if matchRule_name(nodeO, nodeR, matcher, recLevel, verbose):
        return True

    # If (incorrectly) parsed as expression, recurse with nodeR=value, nodeO=same
    # elif matchRule_expr(nodeO, nodeR, matcher, recLevel, verbose):
    # #     # pprint(verbose, recLevel, 'expr', nodeR, nodeO)  
    #     return matchRule(nodeO, nodeR[0].value, matcher, recLevel=recLevel+1, verbose=verbose)

    # If list, search for multiple consecutive children
    elif matchRule_list(nodeO, nodeR, matcher, recLevel, verbose):  
        return True
    
    # otherwise, match the type directly
    elif matchRule_type(nodeO, nodeR, matcher, recLevel, verbose):
        return True
    
    # Otherwise, fail by returning None   
    pprint(verbose, recLevel, 'fail', nodeR, nodeO)   
    return None

#endregion

#region: Match NodeO (original) recursively

def matchOrig(tree, rule, nodeO=None, nodeR=None, verbose=False):    
    '''Recursively match parse of original code and rule template.
Each recursion step goes within original code's AST.
OrigP = Complete AST, rule = Rule object
nodeO = current AST node, nodeR = current rule node'''

    # init recursion
    replacedNodes = []
    if nodeO is None: nodeO = tree
    if nodeR is None: nodeR = rule.match
    
    # match current-orig and rule-node
    matcher = Matcher()
    matchRule(nodeO, nodeR, matcher, verbose=verbose) 

    # If success (replHash not empty), apply rule action
    for match in matcher.matches:
        if match.success:            
            treeCopy, nodeCopy = ruleAction.applyAction(tree, rule, nodeO, match.replHash, match.delNodes, verbose=verbose)        
            replacedNodes.append(treeCopy) # Add the modified tree to return list          

    # recurse original code tree
    if hasattr(nodeO, 'body'): # If there exists a 'body'
        for i in nodeO.body: # For each childNode inside the body
            tree, nodeO, newReplNodes = matchOrig(tree, rule, i, nodeR, verbose=verbose) # match ruleP against child
            replacedNodes += newReplNodes
    
    return tree, nodeO, replacedNodes
#endregion  
 