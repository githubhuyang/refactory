# Developers:   Yang Hu, et al.
# Email:    huyang0905@gmail.com

import os
import numpy
from basic_framework.utils import unwrapper
from basic_framework.utils import regularize
from basic_framework.statement import get_token_list


def gen_feedback(ss_list):
    fb_list = []
    fb_score_list = []
    for ss in ss_list:
        if len(ss.ss_dict.keys()) == 0:
            continue
        fb_dict = {}
        score_list = []
        for ln in ss.ss_dict.keys():
            if len(ss.ss_dict[ln]) == 0:
                continue
            choice = ss.score_dict[ln].index(max(ss.score_dict[ln]))
            expr = ss.ss_dict[ln][choice]
            score = ss.score_dict[ln][choice]

            fb_dict[ln] = unwrapper(expr)
            score_list.append(score)
        fb_list.append(fb_dict)
        fb_score_list.append(numpy.sum(score_list))
    return fb_list, fb_score_list


def gen_rep_code(ss_list, holed_func_code):
    assert(len(ss_list) > 0)
    fb_list, fb_score_list = gen_feedback(ss_list)

    if len(fb_score_list) == 0:
        return ""

    choice = fb_score_list.index(max(fb_score_list))
    fb = fb_list[choice]

    rep_code = ""
    for line in holed_func_code.split("\n"):
        if "Holes.iil_hole(" in line or \
                "Holes.empty_hole(" in line or \
                "from basic_framework.holes import *" in line:
            continue
        else:
            hole_sig_str = "Holes.condition_hole("
            ind = line.find(hole_sig_str)
            if ind != -1:
                front_str = line[:ind]
                ln = float(line[ind + len(hole_sig_str):].split(",")[0])
                rep_code += front_str + fb[ln] + ":\n"
                continue

            hole_sig_str = "Holes.assign_hole("
            ind = line.find(hole_sig_str)
            if ind != -1:
                front_str = line[:ind]
                ln = float(line[ind + len(hole_sig_str):].split(",")[0])
                rep_code += front_str + fb[ln] + "\n"
                continue

            hole_sig_str = "Holes.simple_assign_hole("
            ind = line.find(hole_sig_str)
            if ind != -1:
                front_str = line[:ind]
                ln = float(line[ind + len(hole_sig_str):].split(",")[0])
                rep_code += front_str + fb[ln] + "\n"
                continue

            hole_sig_str = "Holes.init_hole("
            ind = line.find(hole_sig_str)
            if ind != -1:
                front_str = line[:ind]
                ln = float(line[ind + len(hole_sig_str):].split(",")[0])
                rep_code += front_str + fb[ln] + "\n"
                continue

            rep_code += line + "\n"

    final_rep_code = ""
    line_list = rep_code.split("\n")[:-1]
    for line in line_list:
        while True:
            frt_str = "var_dict[\""
            end_str = "\"]"
            l = line.find(frt_str)
            if l == -1:
                break
            else:
                r = l + len(frt_str) + line[l + len(frt_str):].find(end_str)
                line = line[:l] + line[l + len(frt_str):r].strip() + line[r + len(end_str):]
        final_rep_code += line + "\n"
    final_rep_code = regularize(final_rep_code)
    return final_rep_code