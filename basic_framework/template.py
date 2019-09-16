# Developers:   Yang Hu, et al.
# Email:    huyang0905@gmail.com

from basic_framework.utils import *
from basic_framework.statement import *


def get_temp_cons_lists(corr_code_list):
    ref_temp_list = []
    ref_const_list = []

    
    for corr_code in corr_code_list:
        ref_stat_vari_names = get_vari_names(corr_code)

        for var_num, temp in ext_temp_list(corr_code, ref_stat_vari_names):
            added = False
            for var_num_added, temp_added in ref_temp_list:
                if var_num_added == var_num and temp_added == temp:
                    added = True
                    break
            if not added:
                ref_temp_list.append([var_num, temp])
        for const in ext_const_list(corr_code):
            if const not in ref_const_list:
                ref_const_list.append(const)
    return ref_temp_list, ref_const_list


def ext_temp_list(code, vari_set):
    temp_list = []

    code = regularize(code)
    line_list = code.split("\n")[:-1]

    temp_set = set()
    for line in line_list:
        token_list = get_token_list(line)

        key_word_begin = ""
        key_word_end = ""
        if is_if_stat(line):
            key_word_begin = "if"
            key_word_end = ":"
        elif is_elif_stat(line):
            key_word_begin = "elif"
            key_word_end = ":"
        elif is_while_loop_stat(line):
            key_word_begin = "while"
            key_word_end = ":"
        elif is_assign_stat(line):
            if any([token.string=="return" for token in token_list]):
                key_word_begin = "return"
                key_word_end = None
            else:
                for token in token_list:
                    if token.string in ["=", "+=", "-=", "*=", "/="]:
                        key_word_begin = token.string
                        key_word_end = None
                        break
        else:
            continue

        token_list = get_token_list(line)
        r1 = -1
        l2 = -1
        _, r1 = get_token_range(token_list, key_word_begin)
        if key_word_end is None:
            l2 = len(line)
        else:
            l2, _ = get_token_range(token_list, key_word_end)
        cond_str = line[r1:l2].strip()
        vari_num, temp = ext_temp(cond_str, vari_set)
        if temp not in temp_set:
            temp_set.add(temp)
            temp_list.append([vari_num, temp])
    return temp_list


def ext_temp(expr, vari_set):
    expr = expr.strip()
    token_list = get_token_list(expr)
    vari_num = 0
    vari_name_map = {}

    template = ""
    for token in token_list:
        if token.string in vari_set:
            if token.string not in vari_name_map.keys():
                vari_name_map[token.string] = vari_num
                template += "{" + str(vari_num) + "}" + " "
                vari_num += 1
            else:
                template += "{" + str(vari_name_map[token.string]) + "}" + " "
        else:
            template += token.string + " "
    return vari_num, template


def ext_const_list(code):
    const_list = []
    code = regularize(code)
    line_list = code.split("\n")[:-1]
    for line in line_list:
        token_list = get_token_list(line)
        for token in token_list:
            if tok_name[token.exact_type] in ["STRING", "NUMBER"]:
                const_list.append(token.string)
    return const_list