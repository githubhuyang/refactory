import ast

from basic_framework.refactoring_ast import controlFlow as CF

class Rule:
    def __init__(self, name, matchC, actionC):
        self.name = name
        self.matchC = matchC
        self.actionC = actionC
        
        self.match = ast.parse(matchC).body # Ignore the 'module' wrapper
        self.action = ast.parse(actionC).body # In rule creation

rules = []

'''Legend:
BLOCK_X => One or more statements
JUMP_BLOCK_X => One or more statements, one of which is a jump instruction (return/continue/break)
COND_X => Match single condition
STAT_X => Match single statement
'''
#region: Category-A Existing conditional transformations

    # if(C1) B1 else S -> if(C1) B1; S
rules.append(Rule('A1.a', '''
if COND_1: 
    BLOCK_1
else: 
    BLOCK_S''', '''
if COND_1: 
    BLOCK_1
BLOCK_S'''))

    # if(C1) B1; S -> if(C1) B1 else S
rules.append(Rule('A1.b', '''
if COND_1: 
    JUMP_BLOCK_1
BLOCK_S''', '''
if COND_1: 
    JUMP_BLOCK_1
else: 
    BLOCK_S'''))

    # if(C1) if(C2) B1 -> if(C1 and C2) B1 
rules.append(Rule('A2.c', '''
if COND_1: 
    if COND_2:
        BLOCK_1''', '''
if COND_1 and COND_2: 
    BLOCK_1'''))

    # if(C1 and C2) B1 -> if(C1) if(C2) B1
rules.append(Rule('A2.d', '''
if COND_1 and COND_2: 
    BLOCK_1''', '''
if COND_1: 
    if COND_2:
        BLOCK_1'''))

#endregion

#region: Category-B New conditional transformations
    # S1 -> if True: S1

rules.append(Rule('B1.f', '''
BLOCK_S''', '''
if True: 
    BLOCK_S'''))

rules.append(Rule('B1.g', '''
BLOCK_S''', '''
if False: 
    pass
BLOCK_S'''))

rules.append(Rule('B1.h', '''
BLOCK_S''', '''
if True: 
    pass
BLOCK_S'''))

rules.append(Rule('B2.j', '''
if COND_1:
    BLOCK_1''', '''
if COND_1: 
    BLOCK_1
elif False:
    pass'''))

rules.append(Rule('B2.k', '''
if COND_1:
    BLOCK_1''', '''
if COND_1: 
    BLOCK_1
elif True:
    pass'''))

    # if(C1) B1 -> if(C1) B1 else pass
rules.append(Rule('B2.l', '''
if COND_1:
    BLOCK_1''', '''
if COND_1: 
    BLOCK_1
else:
    pass'''))


#endregion

#region: Category-C Loop guards
    # for i in I: S1 -> if len(I)>0: for i in I: S1
rules.append(Rule('C1.n', '''
for INDEX in ITERATOR:
    BLOCK_1''', '''
if len(ITERATOR) > 0:    
    for INDEX in ITERATOR:
        BLOCK_1'''))

    # for i in I: S1 -> if len(I)==0: pass; else: for i in I: S1
rules.append(Rule('C1.o', '''
for INDEX in ITERATOR:
    BLOCK_1''', '''
if len(ITERATOR) == 0:    
    pass
else:
    for INDEX in ITERATOR:
        BLOCK_1'''))

    # while i < len(I): S1 -> if len(I)>0: while i < len(I): S1
rules.append(Rule('C2.q', '''
while INDEX < len(ITERATOR):
    BLOCK_1''', '''
if len(ITERATOR) > 0:    
    while INDEX < len(ITERATOR):
        BLOCK_1'''))

    # while i < len(I): S1 -> if len(I)==0: pass; else: while i < len(I): S1
rules.append(Rule('C2.r', '''
while INDEX < len(ITERATOR):
    BLOCK_1''', '''
if len(ITERATOR) == 0:    
    pass
else:
    while INDEX < len(ITERATOR):
        BLOCK_1'''))

#endregion

#region: Category-D While Loop Transformation
    # while C1: B1 -> while True: if Not C1: break; B1
rules.append(Rule('D1.t', '''
while CONDITION_1:
    BLOCK_1''', '''
while True:
    if not CONDITION_1:    
        break
    BLOCK_1'''))

    # while C1: B1 Return -> if C1: B1 Return
rules.append(Rule('D2.v', '''
while CONDITION_1:
    RETURN_BLOCK_1''', '''
if CONDITION_1:    
    RETURN_BLOCK_1'''))

    # while C1: B1 break -> if C1: B1
rules.append(Rule('D3.x', '''
while CONDITION_1:
    BREAK_BLOCK_1''', '''
if CONDITION_1:    
    BREAK_BLOCK_1'''))

#endregion

#region: Category-E Loop unrolling
    # for i in I: S1 -> for i in I[:len(I)/2]: S1; for i in I[len(I)/2:]: S1
rules.append(Rule('E1.z', '''
for INDEX in ITERATOR:
    BLOCK_1''', '''
for INDEX in ITERATOR[:int(len(ITERATOR)/2)]:
    BLOCK_1
for INDEX in ITERATOR[int(len(ITERATOR)/2):]:
    BLOCK_1'''))

#endregion