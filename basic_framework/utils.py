# Developers:   Yang Hu, et al.
# Email:    huyang0905@gmail.com

import os
import gc
import sys
import ast
import astunparse
import psutil
import traceback
import autopep8
from multiprocessing import Process, Queue
from basic_framework.statement import *


def unwrapper(expr):
    wrap_left_str = "var_dict[\'"
    wrap_right_str = "\']"
    while True:
        l1 = expr.find(wrap_left_str)
        if l1 == -1:
            break
        else:
            left_part = expr[:l1]
            cond_right = expr[l1 + len(wrap_left_str):]
            l2 = cond_right.find(wrap_right_str)
            if l2 == -1:
                print("unwrapper: something wrong")
                break
            else:
                mid_part = cond_right[:l2]
                right_part = cond_right[l2 + len(wrap_right_str):]
                expr = left_part + mid_part + right_part
    return expr


def safe_eval_list(expr_list, score_list, var_dict, mpq):
    for i in range(len(expr_list)):
        expr = expr_list[i]
        score = score_list[i]
        try:
            expr_res = eval(expr)
            mpq.put((expr, score, expr_res))
        except:
            mpq.put((expr, score, None))


class FastEvaluator:

    def parallel_eval(self, expr_list, score_list, var_dict, n_jobs=8):

        relation_dict = {}
        score_dict = {}
        result_dict = {}

        seg_len = len(expr_list) // n_jobs + 1

        sys.setrecursionlimit(1000000)

        p_list = []
        mpq_list = []
        try:
            for i in range(n_jobs):
                part_expr_list = expr_list[seg_len * i: seg_len * (i + 1)]
                part_score_list = score_list[seg_len * i: seg_len * (i + 1)]
                mpq = Queue()
                p = Process(target=safe_eval_list, args=(part_expr_list, part_score_list, var_dict, mpq))
                p_list.append(p)
                mpq_list.append(mpq)

            for p in p_list:
                p.start()

            while True:
                all_dead = not any(p.is_alive() for p in p_list)
                exists_dead = any(not p.is_alive() for p in p_list)
                all_empty = all(mpq.empty() for mpq in mpq_list)
                if all_dead and all_empty:
                    break
                elif exists_dead:
                    c = 0
                    for i in range(len(p_list)):
                        if p_list[i].is_alive():
                            continue
                        mpq = mpq_list[i]
                        if not mpq.empty():
                            expr, score, expr_res = mpq.get()
                            result_dict[expr] = expr_res
                            if expr_res is not None:

                                try:
                                    relation_dict[expr_res] = relation_dict[expr_res]
                                except:
                                    is_add = True
                                    for res_key, expr_list in relation_dict.items():
                                        if len(expr_list) > 0:
                                            res = result_dict[expr_list[0]]
                                            if res == expr_res:
                                                expr_res = res_key
                                                is_add = False
                                                break
                                    if is_add:
                                        expr_res = expr

                                if expr_res not in relation_dict.keys():
                                    relation_dict[expr_res] = []
                                if expr_res not in score_dict.keys():
                                    score_dict[expr_res] = []
                                relation_dict[expr_res].append(expr)
                                score_dict[expr_res].append(score)
                            c = c + 1
        except:
            traceback.print_exc(file=sys.stderr)
        for mpq in mpq_list:
            mpq.close()

        return relation_dict, score_dict


def rm_bb_indent(bb_code):
    new_bb_code = ""
    curr_ind_list = []
    for line in bb_code.split("\n"):
        if len(line) == 0:
            continue

        curr_ind_list.append(get_indent(line))
        new_line = rm_indent(line)
        new_bb_code += new_line + "\n"

    assert(len(set(curr_ind_list)) <= 1)

    ind = 0
    if len(curr_ind_list) > 0:
        ind = curr_ind_list[0]

    return new_bb_code, ind


def resume_bb_indent(bb_code, ind):
    new_bb_code = ""
    ind_str = "".join([" " for tmp in range(ind)])
    for line in bb_code.split("\n"):
        if len(line) == 0:
            continue

        new_line = ind_str + line
        new_bb_code += new_line + "\n"
    return new_bb_code


def regularize(code):
    '''change code style (tab to space)'''
    # remove comment
    code = astunparse.unparse(ast.parse(code))

    # put logical lines into one physical line
    token_list = get_token_list(code)

    new_code = ""
    tmp_list = []
    indent_str = ""

    new_line_flag = False
    for token in token_list:
        if tok_name[token.exact_type] in ["NEWLINE", "ENDMARKER"]:
            new_code += indent_str + " ".join([tmp_token.string for tmp_token in tmp_list]) + "\n"
            tmp_list = []
            new_line_flag = True
        elif tok_name[token.exact_type] == "NL":
            pass
        elif tok_name[token.exact_type] == "COMMENT":
            pass
        elif tok_name[token.exact_type] == "INDENT":
            indent_str += "    "
        elif tok_name[token.exact_type] == "DEDENT":
            if new_line_flag:
                indent_str = indent_str[:-4]
        else:
            new_line_flag = False
            tmp_list.append(token)

    final_code = ""
    for line in new_code.split("\n"):

        token_list = get_token_list(line)
        if any([token.string in ["from", "import"] for token in token_list]):
            pass
        else:
            if get_indent(line) == 0 and \
                len(token_list) > 1 and \
                    all([token.string != "def" for token in token_list]):
                pass
            else:
                final_code += line + "\n"

    return final_code


def get_vari_names(code):
    vari_name_list = []
    root = ast.parse(code)
    for node in ast.walk(root):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            vari_name_list.append(str(node.id))
        elif isinstance(node, ast.arg):
            vari_name_list.append(str(node.arg))
    vari_name_list = list(set(vari_name_list))
    return vari_name_list


def swt_func_vn(func_code, vn_map):
    class VMTransformer(ast.NodeTransformer):
        def __init__(self, n_map):
            self.__n_map = n_map
            super()

        def visit_Name(self, node):
            if node.id in self.__n_map.keys():
                node.id = self.__n_map[node.id]
            return node

        def visit_arg(self, node):
            if node.arg in self.__n_map.keys():
                node.arg = self.__n_map[node.arg]
            return node

    tree = ast.parse(func_code)

    vmt = VMTransformer(vn_map)
    swt_tree = vmt.visit(tree)

    swt_func_code = astunparse.unparse(swt_tree)
    return regularize(swt_func_code)


def syntax_check(code):
    try:
        compile(code, "<string>", "exec")
        return True
    except:
        return False