# Developers:   Yang Hu, et al.
# Email:    huyang0905@gmail.com

import re
from fastcache import clru_cache
import ast
import astunparse
from token import *
from io import StringIO
from tokenize import generate_tokens

# get indentation from a statement
def get_indent(statement):
    token_list = get_token_list(statement)
    for i in range(len(token_list)):
        token = token_list[i]
        if tok_name[token.exact_type] == "INDENT":
            return token.end[1]
    c = 0
    for i in range(len(statement)):
        if statement[i] in ["\t", " "]:  # "\n"
            c += 1
        else:
            break
    return c


def rm_indent(statement):
    return statement.strip()


# get token list from a expression or statement
@clru_cache(maxsize=256)
def get_token_list(statement):
    token_list = []
    try:
        token_list.extend(list(generate_tokens(StringIO(statement).readline)))
    except Exception as e:
        pass
    return token_list


def get_token_range(token_list, token_name):
    for token in token_list:
        if token.string == token_name:
            return token.start[1], token.end[1]
    return -1, -1


# judge the type of a statement
def is_cond_stat(statement):
    return is_if_stat(statement) or is_elif_stat(statement) or is_while_loop_stat(statement)


def is_loop_stat(statement):
    return is_for_loop_stat(statement) or is_while_loop_stat(statement)


def is_if_stat(statement):
    statement = statement.strip()
    token_list = get_token_list(statement)

    if len(token_list) == 0:
        return False
    if token_list[0].string == "if":
        return True
    return False


def is_elif_stat(statement):
    statement = statement.strip()
    token_list = get_token_list(statement)
    if len(token_list) == 0:
        return False
    if token_list[0].string == "elif":
        return True
    return False


def is_else_stat(statement):
        statement = statement.strip()
        token_list = get_token_list(statement)
        if len(token_list) == 0:
            return False
        if token_list[0].string == "else":
            return True
        return False


def is_for_loop_stat(statement):
    statement = statement.strip()
    token_list = get_token_list(statement)
    if len(token_list) == 0:
        return False
    if token_list[0].string == "for":
        return True
    return False


def is_while_loop_stat(statement):
    statement = statement.strip()
    token_list = get_token_list(statement)
    if len(token_list) == 0:
        return False
    if token_list[0].string == "while":
        return True
    return False


def is_token_in_stat(statement, token_str):
    token_list = get_token_list(statement)
    for token in token_list:
        if token.string == token_str:
            return True
    return False


def is_assign_stat(statement):
    token_list = get_token_list(statement)
    for token in token_list:
        if tok_name[token.exact_type] in ["EQUAL","PLUSEQUAL","MINEQUAL","STAREQUAL","SLASHEQUAL"] and \
            token.string in ["=", "+=", "-=", "*=", "/="]:
            return True
        elif token.string == "return":
            return True
    return False


def is_method_sign(statement):
    token_list = get_token_list(statement)
    for token in token_list:
        if token.string == "def":
            return True
    return False


re_method_call = re.compile("\w*\(")
def has_method_call(statement):
    m = re_method_call.search(statement)
    return m is not None and not is_method_sign(statement)


def get_vari_in_sig(statement):
    vari_list = []
    token_list = get_token_list(statement)
    for i in range(len(token_list)):
        token = token_list[i]
        if token.string == "def":
            l = statement.find("(")
            r = statement.rfind(")")
            statement = statement[l:r + 1]
            token_list_b = get_token_list(statement)
            for token_b in token_list_b:
                if tok_name[token_b.exact_type] == "NAME":
                    vari_list.append(token_b.string)
    return vari_list


def get_vari_in_for(statement):

    vari_list = []

    token_list = get_token_list(statement)

    is_beg_var_rcgn = False
    for i in range(len(token_list)):
        token = token_list[i]
        if token.string == "for":
            is_beg_var_rcgn = True
        elif token.string == "in":
            is_beg_var_rcgn = False
        elif is_beg_var_rcgn:
            if token.string != ",":
                vari_list.append(token.string)
    return vari_list