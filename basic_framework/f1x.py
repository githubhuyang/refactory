# Developers:   Yang Hu, et al.
# Email:    huyang0905@gmail.com

import sys
import inspect
import traceback
import math
import copy
import operator
from basic_framework.utils import FastEvaluator, unwrapper
from basic_framework.exec import fast_eval
import collections
from itertools import combinations, permutations
from basic_framework.distance import lev_code_distance
from basic_framework.statement import *

class DepthTrace:
    """Restrain the times that a program invokes a hole method"""
    MAX_DEPTH = 10000000#100

    def __init__(self):
        self.set_max_depth()
        self.STACK_MAX_DEPTH = sys.getrecursionlimit()

    def set_max_depth(self):
        """Set up the maximal times that a program invokes a hole method"""
        self.t_count = DepthTrace.MAX_DEPTH

    def get_stack_size(self):
        """Get stack size faster than len(inspect.stack())"""
        size = 2
        while True:
            try:
                sys._getframe(size)
                size += 1
            except ValueError:
                return size - 1

    def update_times(self):
        """Raise an exception when no further hole method invocation is allowed or stack overflow may happen"""
        if self.t_count <= 0 or \
                self.get_stack_size() >= self.STACK_MAX_DEPTH/2:
            raise DepthTrace.MaxDepthException()
        self.t_count -= 1

    def get_times(self):
        return self.t_count

    class MaxDepthException(Exception):
        pass


class SearchSpaceList:
    def __init__(self):
        self.ss_list = []

    def is_contain(self, ss_a):
        for ss_b in self.ss_list:
            if ss_a.cmp_ss(ss_b):
                return True
        return False

    def get_ss_list(self):
        return self.ss_list

    def add_ss(self, ss):
        self.ss_list.append(ss)


class SearchSpace:
    def __init__(self):
        self.ss_dict = {}
        self.score_dict = {}

    def cmp_ss(self, ss_b):
        u_set = set()
        a_set = set(self.ss_dict.keys())
        u_set = u_set.union(a_set)
        b_set = set(ss_b.ss_dict.keys())
        u_set = u_set.union(b_set)

        for ln in u_set:
            if ln not in a_set or \
                ln not in b_set or \
                set(self.ss_dict[ln]) != set(ss_b.ss_dict[ln]):
                return False
        return True

    def get_expr_list(self, ln):
        if self.ln_exists(ln):
            return self.ss_dict[ln]
        else:
            return None

    def get_score_list(self, ln):
        if self.ln_exists(ln):
            return self.score_dict[ln]
        else:
            return None

    def get_repr_expr(self, ln):
        expr_list = self.ss_dict[ln]
        score_list = self.score_dict[ln]
        return expr_list[score_list.index(max(score_list))]

    def ln_exists(self, ln):
        if ln in self.ss_dict.keys():
            return True
        return False

    def add_expr_list_ws(self, ln, expr_list, score_list):
        """Get the expr list and its corresponding score list"""
        for i in range(len(expr_list)):
            expr = expr_list[i]
            score = score_list[i]
            self.add_expr(ln, expr, score)

    def add_expr(self, ln, expr, score):
        if ln not in self.ss_dict.keys():
            self.ss_dict[ln] = []
            self.score_dict[ln] = []
        self.ss_dict[ln].append(expr)
        self.score_dict[ln].append(score)


class ExprGenerator:

    def __init__(self):
        self.expr_list_dict = {}
        self.type_dict_dict = {}

    def has_call(self, expr):
        class FuncVisitor(ast.NodeVisitor):
            def __init__(self):
                super()
                self.has_call = False

            def visit_Call(self, node):
                self.has_call = True

            def run(self, expr):
                n = ast.parse(expr)
                self.visit(n)
                return self.has_call

        return FuncVisitor().run(expr)

    def gen_expr_list_from_templates(self, var_dict):
        from basic_framework.holes import Holes

        expr_list = []
        type_dict = {}

        vari_nam_list = list(var_dict.keys())
        for vari_num, template_str in Holes.template_list:
            vari_tuple_list = list(combinations(vari_nam_list, vari_num))

            for vari_tuple in vari_tuple_list:
                vari_tuple_perm_list = permutations(list(vari_tuple), len(vari_tuple))

                for vari_tuple_perm in vari_tuple_perm_list:
                    tmp_expr = template_str
                    for i in range(len(vari_tuple_perm)):
                        tmp_expr = tmp_expr.replace("{" + str(i) + "}", "var_dict['" + vari_tuple_perm[i] + "']")

                    if "**" in tmp_expr:
                        pass
                    elif self.has_call(tmp_expr):
                        pass
                    else:
                        try:
                            res = fast_eval(tmp_expr, var_dict)
                            type_dict[tmp_expr] = str(type(res))
                            expr_list.append(tmp_expr)
                        except Exception as e:
                            pass


        return expr_list, type_dict

    def gen_expr_list(self, var_dict, is_simple=False):
        expr_list, type_dict = self.gen_expr_list_from_templates(var_dict)
        filter_expr_list = []
        filter_type_dict = {}
        for expr in expr_list:
            if type_dict[expr] != "<class 'bool'>":
                filter_expr_list.append(expr)
                filter_type_dict[expr] = type_dict[expr]

        return filter_expr_list, filter_type_dict


    def gen_assign_ss(self, pre_assign_str, var_dict, k_best, is_simple=False):
        # Generate expressions for the assignment statement
        expr_list = []
        expr_list.append(pre_assign_str)

        # Get the type of the statement in pre_assign_str
        pre_assign_type_str = ""
        try:
            pre_assign_type_str = str(type(fast_eval(pre_assign_str, var_dict)))#copy.deepcopy(
        except Exception:
            pre_assign_type_str = ""

        # Extract method signature
        token_list = get_token_list(pre_assign_str)
        t_start = -1
        t_end = -1
        for i in range(len(token_list)):
            token = token_list[i]
            if token.string == "self" and tok_name[token.exact_type] == "NAME":
                t_start = token.end[1] + 1
            elif token.string == "(" and tok_name[token.exact_type] == "LPAR":
                t_end = token.start[1]
                break
        # If we find a method invocation, we do not change the assignment statement.
        if t_start > -1 and t_end > -1:
            method_signature = pre_assign_str[t_start:t_end]
            if method_signature in dir(var_dict['self']):
                return expr_list, [1]

        expr_list_gen = []
        type_dict = {}

        expr_list_gen, type_dict = self.gen_expr_list(var_dict, is_simple=is_simple)

        for expr in expr_list_gen:
            expr_list.append(expr)

        # Misuse based expression
        from basic_framework.holes import Holes
        for constant in Holes.constant_list:
            for i in range(len(token_list)):
                token = token_list[i]
                if tok_name[token.exact_type] in ["NUMBER", "STRING"]:
                    tmp_cond = pre_assign_str[:token.start[1]] + constant + pre_assign_str[token.end[1]:]
                    expr_list.append(tmp_cond)

        expr_list = list(set(expr_list))

        # Sort and filter
        r_expr_list, r_score_list = self.sort(expr_list, pre_assign_str, var_dict, k_best)
        return r_expr_list, r_score_list

    def gen_misuse_conds(self, pre_cond_str, op_list):
        cond_set = set()
        token_list = get_token_list(pre_cond_str)
        for i in range(len(token_list)):
            token = token_list[i]
            if token.string in op_list:
                t_start = token.start[1]
                t_end = token.end[1]
                if token.string == "is":
                    next_token = token_list[i + 1]
                    if next_token.string == "not" and \
                            tok_name[next_token.exact_type] == "NAME":
                        t_end = next_token.end[1]
                        i += 1
                for op in op_list:
                    cond = pre_cond_str[:t_start] + op + pre_cond_str[t_end:]
                    cond_set.add(cond)

        from basic_framework.holes import Holes
        for constant in Holes.constant_list:
            for i in range(len(token_list)):
                token = token_list[i]
                if tok_name[token.exact_type] in ["NUMBER", "STRING"]:
                    tmp_cond = pre_cond_str[:token.start[1]] + constant + pre_cond_str[token.end[1]:]
                    cond_set.add(tmp_cond)
        return list(cond_set)

    def gen_cond_ss(self, pre_cond_str, var_dict, k_best):
        cond_list = []
        cond_list.append(pre_cond_str)

        # Add True and False as two condition candidates
        cond_list.append("True")
        cond_list.append("False")

        # Add conditions in correct programs
        expr_list, type_dict = self.gen_expr_list_from_templates(var_dict)
        for expr in expr_list:
            if type_dict[expr] == "<class 'bool'>":
                cond_list.append(expr)

        # Generate condition candidates
        op_list = ["<", "<=", ">", ">=", "==", "!=", "is", "is not"]
        misuse_cond_list = self.gen_misuse_conds(pre_cond_str, op_list)
        cond_list.extend(misuse_cond_list)


        # Remove repeated condations
        cond_list = list(set(cond_list))

        # Sort and filter
        r_cond_list, r_score_list = self.sort(cond_list, pre_cond_str, var_dict, k_best)
        return r_cond_list, r_score_list

    def trans(self, var_str):
        return "var_dict[\'" + var_str + "\']"

    def unwrap_expr(self, expr_str, var_dict):
        rev_var_dict = {}
        for k in var_dict.keys():
            rev_var_dict["var_dict[\'" + k + "\']"] = k

        for wrap_var_str, ori_var_str in rev_var_dict.items():
            if wrap_var_str in expr_str:
                expr_str = expr_str.replace(wrap_var_str, ori_var_str)
        return expr_str

    def score(self, expr_str, ori_expr):
        s0 = 1 /(lev_code_distance(expr_str, ori_expr)+1)
        return s0

    def sort(self, expr_list, ori_expr, var_dict, k_best):
        ori_expr_uw = self.unwrap_expr(ori_expr, var_dict)

        score_list = []
        for i in range(len(expr_list)):
            expr = expr_list[i]
            expr_uw = self.unwrap_expr(expr, var_dict)
            score_list.append([expr, self.score(expr_uw, ori_expr_uw)])

        sorted_res_list = sorted(score_list, key=operator.itemgetter(1), reverse=True)

        res_expr_list = []
        res_score_list = []
        for i in range(len(sorted_res_list)):
            res_expr = sorted_res_list[i][0]
            res_expr_list.append(res_expr)
            score = sorted_res_list[i][1]
            res_score_list.append(score)
        return res_expr_list[:k_best], res_score_list[:k_best]


class ExprRecord:
    def __init__(self):
        self.expr = ""
        self.repr_expr_list = []
        self.repr_score_list = []


class TERelation:

    def __init__(self):
        self.relation_dict = {}
        self.score_dict = {}
        self.result_dict = {}

    def clear(self):
        self.relation_dict = {}
        self.score_dict = {}
        self.result_dict = {}

    def add_expr_list_ws_p(self, expr_list, score_list, var_dict):
        if len(expr_list) == 1:
            self.relation_dict = {expr_list[0]:[expr_list[0]]}
            self.score_dict = {expr_list[0]:[score_list[0]]}
        else:
            self.add_expr_list_ws(expr_list, score_list, var_dict)

    def add_expr_list_ws(self, expr_list, score_list, var_dict):
        import basic_framework.holes as bfh

        bk_var_dict = copy.deepcopy(var_dict)
        for i in range(len(expr_list)):
            expr = expr_list[i]
            score = score_list[i]
            var_dict = copy.deepcopy(bk_var_dict)
            self.add_expr(expr, score, var_dict)
            bfh.Holes.mg.memory_guarder()

    def add_expr(self, expr, score, var_dict):
        try:
            expr_res = fast_eval(expr, var_dict)

            if expr_res is not None:
                self.result_dict[expr] = expr_res
                if not isinstance(expr_res, collections.Hashable):
                    not_add = True
                    for res_key, expr_list in self.relation_dict.items():
                        if len(expr_list) > 0:
                            res = self.result_dict[expr_list[0]]
                            if expr_res == res:
                                expr_res = res_key
                                not_add = False
                                break
                    if not_add:
                        expr_res = expr
                if expr_res not in self.relation_dict.keys():
                    self.relation_dict[expr_res] = []
                if expr_res not in self.score_dict.keys():
                    self.score_dict[expr_res] = []
                self.relation_dict[expr_res].append(expr)
                self.score_dict[expr_res].append(score)
        except Exception:
            pass

    def get_repr_expr(self, expr_res):
        best_expr = ""
        best_score = -1
        for i in range(len(self.relation_dict[expr_res])):
            expr = self.relation_dict[expr_res][i]
            score = self.score_dict[expr_res][i]
            if score > best_score:
                best_expr = expr
                best_score = score
        return best_expr

    def get_expr_rec_list(self):
        expr_rec_list = []
        for expr_res in self.relation_dict.keys():
            repr_expr = self.get_repr_expr(expr_res)
            expr_list = self.relation_dict[expr_res]
            score_list = self.score_dict[expr_res]

            er = ExprRecord()
            er.expr = repr_expr
            er.repr_expr_list = expr_list
            er.repr_score_list = score_list

            expr_rec_list.append(er)
        return expr_rec_list

class ExprGroupList:
    def __init__(self):
        self.expr_group_list = []
        self.index = 0

    def add_expr_rec_list(self, times, ln, expr_rec_list):
        if len(self.expr_group_list) == 0:
            eg_tmp = ExprGroup()
            eg_tmp.add_expr_rec_list(times, ln, expr_rec_list)
            self.add_expr_group(eg_tmp)
        else:
            self.expr_group_list[self.index].add_expr_rec_list(times, ln, expr_rec_list)

    def lt_exists(self, times, ln):
        if len(self.expr_group_list) == 0:
            return False
        elif self.expr_group_list[self.index].lt_exists(times, ln):
            return True
        else:
            return False

    def clear(self):
        self.expr_group_list = []
        self.index = 0

    def add_expr_group(self, expr_group):
        self.expr_group_list.append(expr_group)

    def get_expr_rec_dict(self):
        if self.index >= len(self.expr_group_list):
            return {}
        return self.expr_group_list[self.index].get_expr_rec_dict()

    def get_expr_rec(self, times, ln):
        if self.index >= len(self.expr_group_list):
            return None
        return self.expr_group_list[self.index].get_expr_rec(times, ln)

    def next(self):
        if self.index >= len(self.expr_group_list):
            return False

        if self.expr_group_list[self.index].next():
            return True
        elif self.index < len(self.expr_group_list) - 1:
            self.index += 1
            return True
        else:
            return False

class ExprGroup:
    def __init__(self):
        self.expr_dict = {}

    def clear(self):
        self.expr_dict = {}

    def lt_exists(self, times, ln):
        if times in self.expr_dict.keys() and self.expr_dict[times][2] == ln:
            return True
        else:
            return False

    def add_expr_rec(self, times, ln, expr_rec):
        if times not in self.expr_dict.keys():
            self.expr_dict[times] = [[], 0, ln]
        assert(self.expr_dict[times][2] == ln)
        self.expr_dict[times][0].append(expr_rec)

    def add_expr_rec_list(self, times, ln, expr_rec_list):
        for expr_rec in expr_rec_list:
            self.add_expr_rec(times, ln, expr_rec)

    def get_expr_rec(self, times, ln):
        expr_list = self.expr_dict[times][0]
        ind = self.expr_dict[times][1]
        if ln == self.expr_dict[times][2]:
            return expr_list[ind]
        else:
            return None

    def get_expr_rec_dict(self):
        res_dict = {}
        for times in self.expr_dict.keys():
            ln = self.expr_dict[times][2]
            if ln not in res_dict.keys():
                res_dict[ln] = {}
            res_dict[ln][times] = self.get_expr_rec(times, ln)
        return res_dict

    def prune(self, times, ln, k_best = 1000):
        self.expr_dict[times][ln][0] = self.expr_dict[times][0][:k_best]
        self.expr_dict[times][ln][1] = 0

    def print_curr_state(self):
        times_list = list(self.expr_dict.keys())
        times_list.sort(reverse=True)
        for times in times_list:
            expr_res_list = self.expr_dict[times][0]
            ind = self.expr_dict[times][1]
            ln = self.expr_dict[times][2]
            print(times, ln, unwrapper(expr_res_list[ind].expr))

    def next(self):
        times_list = list(self.expr_dict.keys())
        if len(times_list) == 0:
            return False
        times_list.sort()
        times = times_list[0]

        self.expr_dict[times][1] += 1
        for j in range(len(times_list)):
            expr_list = self.expr_dict[times_list[j]][0]
            if self.expr_dict[times_list[j]][1] >= len(expr_list):
                self.expr_dict[times_list[j]][1] = 0
                if j >= len(times_list) - 1:
                    return False
                else:
                    self.expr_dict[times_list[j + 1]][1] += 1
                    import basic_framework.holes as bfh
                    if times_list[j] in bfh.Holes.curr_eg.expr_dict.keys():
                        del bfh.Holes.curr_eg.expr_dict[times_list[j]]
        return True