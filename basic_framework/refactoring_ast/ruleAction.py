import ast, astunparse
import copy, keyword, builtins

# region: Helper funcs
def findNode(nodeOrig, currOrig, currCopy):
    '''Starting from tree (and treeCopy), iterate until nodeOrig found.'''    
    if currOrig == nodeOrig:
        return currCopy

    if type(currCopy) is list and type(currOrig) is list:
        for i, j in zip(currOrig, currCopy):
            result = findNode(nodeOrig, i, j)
            if result: return result

    if hasattr(currOrig, '_fields'):
        for field in currOrig._fields: 
            i, j = getattr(currOrig, field), getattr(currCopy, field)
            result = findNode(nodeOrig, i, j)
            if result: return result

    return None

def findNode_replHash(tree, treeCopy, replHash):
    replHashCopy = {}
    for key, value in replHash.items():
        if type(value) is list:
            newVal = [findNode(i, tree, treeCopy) for i in value]
        else:
            newVal = findNode(value, tree, treeCopy)
        
        if newVal:
            replHashCopy[key] = newVal
        
    return replHashCopy

def printTree(node, indent=0):
    '''Given an AST node, print the complete tree structure (with memory references)'''
    print('  '*indent,node)
    if hasattr(node, '_fields'):
        for field in node._fields: 
            if field in ['orelse', 'test']:
                attr = getattr(node, field)
                printTree(attr, indent=indent+1)

    if hasattr(node, 'body'): # If there exists a 'body'
        for child in node.body:
            printTree(child, indent=indent+1)

def prePrint(verbose, replHash, replHashCopy, delNodes, delNodesCopy, tree, treeCopy):
    if verbose:
        print('applyAction.ReplHash-Orig: '); print(replHash)
        print('applyAction.ReplHash-Copy: '); print(replHashCopy)

        print('\napplyAction.DelNode-Orig: '); print(delNodes)
        print('applyAction.DelNode-Copy: '); print(delNodesCopy)

        print('\napplyAction.Tree-Orig: '); printTree(tree)
        print('applyAction.Tree-Copy: '); printTree(treeCopy)

#endregion

#region: Place Holders
def get_value(nodeA):
    '''If nodeA is a placeholder (Expr->Name or Name), returns its value''' 
    if type(nodeA) is ast.Name:
        return nodeA.id
    elif type(nodeA) is ast.Expr and type(nodeA.value) is ast.Name:
        return nodeA.value.id

def get_repl(nodeA, replHash):
    '''Check if node is a placeholder (Expr->Name)''' 
    value = get_value(nodeA)
    if value: 
        if value in replHash: # Check if placeholder exists in replHash
            return replHash[value]
        elif value in keyword.kwlist + dir(builtins): # Is a keyword/builtin?
            return nodeA # Then return the same node
        else: # Else, raise exception
            raise Exception('No match for \'' + value + '\' in replHash=' + str(replHash))

#endregion

#region: Place Holder Replacement
def repl_placeholders(nodeA, replHash):
    '''Replace place holders in rule.action with replHash (found during match)'''
    # If list, replace each indiv element
    if type(nodeA) is list: 
        newNodeA = []

        for ele in nodeA: # For each childNode 
            repl = get_repl(ele, replHash) # Check if exists in replHash
            if repl:
                newNodeA.append(repl) # Add to repl
            else: # else recurse and replace
                newNodeA.append(repl_placeholders(ele, replHash))

        return newNodeA

    # Otherwise, replace each field
    elif hasattr(nodeA, '_fields'): # And match all fields
        for field in nodeA._fields: 
            attr = getattr(nodeA, field)
            repl = get_repl(attr, replHash) # Check if exists in replHash
            if repl:
                setattr(nodeA, field, repl) # repl
            else: # else recurse and replace                
                setattr(nodeA, field, 
                    repl_placeholders(attr, replHash))

    # And return nodeA 
    return nodeA

#endregion

#region: Rule Action
def recurseDel(nodeO, delNode, depth=0):
    '''Recursively delete nodes'''
    #print(nodeO, delNode)
    if 'body' in nodeO._fields:
        if delNode in nodeO.body: # If found
            index = nodeO.body.index(delNode)
            nodeO.body.remove(delNode)
            return index, depth # Return its index and depth
                
        for child in nodeO.body: # Otherwise
            i, depth = recurseDel(child, delNode, depth+1) # Search within its children
            if i is not None:
                return i, depth
    
    return None, depth


def applyAction(tree, rule, nodeO, replHash, delNodes, verbose=False):
    # Return a copy of the tree, and the corresponding "nodeO" in that copy.
    treeCopy = copy.deepcopy(tree)
    nodeCopy = findNode(nodeO, tree, treeCopy) 
    replHashCopy = findNode_replHash(tree, treeCopy, replHash)
    delNodesCopy = [findNode(node, tree, treeCopy) for node in delNodes]
    
    prePrint(verbose, replHash, replHashCopy, delNodes, delNodesCopy, tree, treeCopy)        

    # Delete matched nodes, and record its index
    lowestI = float('inf')
    for delNode in delNodesCopy:
        index, depth = recurseDel(nodeCopy, delNode)
        if index is None:
            raise Exception('DelNode: ', delNode, 'not found in', nodeCopy)
        if depth == 0: # Add index to min, only if when depth = 0
            lowestI = min(lowestI, index) # i.e, delNode found at current tree level (nodeO.body)
        
    
    if lowestI == float('inf'): # If no nodes to del
        lowestI = 0  # Insert at beginning

    # Replace holes in action nodes
    actionNodes = copy.deepcopy(rule.action)
    actionNodes = repl_placeholders(actionNodes, replHashCopy)
    
    # Add Action nodes, at lowestI index
    nodeCopy.body = nodeCopy.body[:lowestI] + actionNodes + nodeCopy.body[lowestI:]
    if verbose:
        print('applyAction.unparse-before:',astunparse.unparse(tree))
        print('applyAction.unparse-after:', astunparse.unparse(treeCopy))

    return treeCopy, nodeCopy
    
#endregion   