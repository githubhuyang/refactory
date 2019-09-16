# Developers:   Yang Hu, et al.
# Email:    huyang0905@gmail.com

import os
import sys
import itertools
import ast
import re
import hashlib
import pickle
from tokenize import tokenize
import time
import keyword
from token import *
from builtins import open as _builtin_open
from basic_framework.f1x import SearchSpaceList, ExprGroup, ExprGenerator, SearchSpace, DepthTrace, TERelation
from basic_framework.utils import FastEvaluator, get_token_list
from basic_framework.exec import MemoryGuarder, fast_eval


class Holes:
    token_list_map = {}

    expr_cache = {}

    is_stop = False

    template_list = []

    constant_list = []

    vari_hist = {}

    hist_stop = False

    mg = MemoryGuarder()

    expr_gen = ExprGenerator()

    ssl = SearchSpaceList() # search space list

    curr_ss = SearchSpace()

    curr_eg = ExprGroup()

    dt = DepthTrace()

    ldt_dict = {} # restrict the loop number

    comp_dict = {}

    curr_tc_id = 0

    in_genhole_time = 0

    real_output = ""

    @classmethod
    def init_global_vars(cls):
        cls.vari_hist = {}
        cls.mg = MemoryGuarder()
        cls.ssl = SearchSpaceList()  # search space list
        cls.curr_ss = SearchSpace()
        cls.curr_eg = ExprGroup()
        cls.expr_gen = ExprGenerator()
        cls.dt = DepthTrace()
        cls.ldt_dict = {}
        cls.comp_dict = {}
        cls.curr_tc_id = 0
        cls.hist_stop = False
        cls.expr_cache = {}
        cls.token_list_map = {}
        cls.in_genhole_time = 0
        cls.real_output = ""

    @classmethod
    def expr_wrapper(cls, expr_str, var_dict):
        token_list = get_token_list(expr_str)

        str_list = []
        last_end = 0
        for i in range(len(token_list)):
            token = token_list[i]
            token_type = token.exact_type
            if tok_name[token_type] == "NAME" and \
                not keyword.iskeyword(token.string) and \
                    token.string in var_dict.keys():
                t_start = token.start[1]
                t_end = token.end[1]
                str_list.append(expr_str[last_end:t_start])

                str_list.append("var_dict[\'" + token.string + "\']")
                last_end = t_end
        str_list.append(expr_str[last_end:])
        return "".join(str_list)

    @classmethod
    def extend_var_dict(cls, var_dict):
        """Add constants, self attributes to var_dict, initialization, etc"""
        # self
        if "self" in var_dict.keys():
            for var_name, var_value in var_dict["self"].__dict__.items():
                var_dict["self." + var_name] = var_value

        return var_dict

    @classmethod
    def generic_hole(cls, ln, pre_expr_str, var_dict, ssf):
        if cls.is_stop:
            raise cls.StopException()

        start_time = time.process_time()

        # Extend var_dict
        var_dict = cls.extend_var_dict(var_dict)

        # Wrap pre_expr_str and get the time of execution
        pre_expr_str = cls.expr_wrapper(pre_expr_str, var_dict)
        times = cls.dt.get_times()

        # Test-equivalent analysis
        if not cls.curr_eg.lt_exists(times, ln):
            expr_list = []
            score_list = []

            times_list = list(cls.curr_eg.expr_dict.keys())
            times_list.sort()
            for times_a in times_list:
                if times_a > times and \
                        ln == cls.curr_eg.expr_dict[times_a][2]:

                    expr_rec = cls.curr_eg.get_expr_rec(times_a, ln)
                    expr_list = expr_rec.repr_expr_list
                    score_list = expr_rec.repr_score_list
                    break
            if len(expr_list) == 0:
                if cls.curr_ss.ln_exists(ln):
                    expr_list = cls.curr_ss.get_expr_list(ln)
                    score_list = cls.curr_ss.get_score_list(ln)
                else:

                    if ssf == "cond":
                        expr_list, score_list = cls.expr_gen.gen_cond_ss(pre_expr_str, var_dict, k_best = 50)
                    elif ssf == "assign":
                        expr_list, score_list = cls.expr_gen.gen_assign_ss(pre_expr_str, var_dict, k_best = 10)
                    elif ssf == "simple_assign":
                        expr_list, score_list = cls.expr_gen.gen_assign_ss(pre_expr_str, var_dict, k_best=5, is_simple=True)
                    elif ssf == "init":
                        expr_list, score_list = cls.expr_gen_init_ss(var_dict)
                    else:
                        raise cls.NoSSException()

            assert (len(expr_list) > 0)
            ter = TERelation()
            ter.add_expr_list_ws_p(expr_list, score_list, var_dict)
            expr_rec_list = ter.get_expr_rec_list()

            if len(expr_rec_list) > 0:
                cls.curr_eg.add_expr_rec_list(times, ln, expr_rec_list)
            else:
                raise cls.NoCandidateException()

        # Select one expr and run
        selected_expr = cls.curr_eg.get_expr_rec(times, ln).expr

        res = fast_eval(selected_expr, var_dict)
        cls.dt.update_times()

        cls.in_genhole_time += (time.process_time() - start_time)
        return res


    @classmethod
    def condition_hole(cls, ln, pre_cond_str, var_dict):
        return cls.generic_hole(ln, pre_cond_str, var_dict, "cond")

    @classmethod
    def simple_assign_hole(cls, ln, pre_assign_str, var_dict):
        return cls.generic_hole(ln, pre_assign_str, var_dict, "simple_assign")

    @classmethod
    def assign_hole(cls, ln, pre_assign_str, var_dict):
        return cls.generic_hole(ln, pre_assign_str, var_dict, "assign")

    @classmethod
    def expr_gen_init_ss(cls, var_dict):
        expr_list = []
        score_list = []
        init_expr_list = ["0", "0.0", "\"\"", "True", "list()", "set()", "dict()", "tuple()"]
        for var_name in var_dict.keys():
            for init_expr in init_expr_list:
                expr_list.append("var_dict[\"" + var_name + "\"] = " + init_expr)
                score_list.append(0.1)
        return expr_list, score_list

    @classmethod
    def init_hole(cls, ln, var_dict):
        return cls.generic_hole(ln, "", var_dict, "init")


    @classmethod
    def method_hole(cls, ln, pre_invoke_str, var_dict):
        return fast_eval(pre_invoke_str, var_dict)

    @classmethod
    def empty_hole(cls):
        return

    @classmethod
    def iil_hole(cls, ln):
        """This hole is used to sense large or infinite loop
            "iil" means "immune to infinite loop"
        """
        if ln not in cls.ldt_dict.keys():
            cls.ldt_dict[ln] = DepthTrace()
            cls.ldt_dict[ln].set_max_depth()
        cls.ldt_dict[ln].update_times()

        if cls.is_stop:
            raise cls.StopException()
        if cls.hist_stop:
            raise cls.HistTLEException()

    class StopException(Exception):
        pass

    @classmethod
    def is_object_equal(cls, object_a, object_b):
        if type(object_a) == type(object_b):
            if object_a == object_b:
                return True
            else:
                return False
        else:
            close_type_list = ["<class 'list'>", "<class 'tuple'>"]
            if str(type(object_a)) in close_type_list and \
                    str(type(object_b)) in close_type_list:
                la = list(object_a)
                lb = list(object_b)
                if la == lb:
                    return True
                else:
                    return False
            else:
                return False

    @classmethod
    def vari_hist_hole(cls, var_dict):
        if cls.is_stop:
            raise cls.StopException()

        if cls.hist_stop:
            raise cls.HistTLEException()

        for k, v in var_dict.items():
            if k not in cls.vari_hist.keys():
                cls.vari_hist[k] = []
            if len(cls.vari_hist[k]) == 0 or \
                    not cls.is_object_equal(cls.vari_hist[k][-1], v):
                cls.vari_hist[k].append(v)

        for k1, v1 in var_dict.items():
            for k2, v2 in var_dict.items():
                if k1 != k2:
                    expr_str = k1 + "[" + k2 + "]"

                    comb_v = None
                    try:
                        comb_v = fast_eval(expr_str, var_dict)
                    except:
                        comb_v = None
                    if comb_v is not None:
                        if expr_str not in cls.vari_hist.keys():
                            cls.vari_hist[expr_str] = []
                        if len(cls.vari_hist[expr_str]) == 0 or not cls.is_object_equal(cls.vari_hist[expr_str][-1], comb_v):
                            cls.vari_hist[expr_str].append(comb_v)


    class HistTLEException(Exception):
        pass

    class NoCandidateException(Exception):
        pass

    class NoSSException(Exception):
        pass