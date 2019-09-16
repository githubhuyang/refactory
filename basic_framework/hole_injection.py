# Developers:   Yang Hu, et al.
# Email:    huyang0905@gmail.com

from basic_framework.statement import *
from basic_framework.cfs import *
from itertools import combinations
import functools
import copy


def add_iil_holes(code):
    sl_map = {}
    line_list = code.split("\n")
    if line_list[-1] == "":
        line_list = line_list[:-1]
    hole_result_code = ""
    for i in range(len(line_list)):
        sl_map[i] = 0.01
        line = line_list[i] + "\n"
        hole_result_code += line

        if is_method_sign(line):
            hole_result_code += "    Holes.iil_hole(" + str(
                i + sl_map[i]) + ")\n"
            sl_map[i] += 0.01

        if is_loop_stat(line):
            ind = get_indent(line_list[i])
            hole_result_code += "".join([" " for k in range(ind)]) + "    Holes.iil_hole(" + str(
                i + sl_map[i]) + ")\n"
            sl_map[i] += 0.01
    return hole_result_code


def add_vari_hist_holes(code, func_name):
    func_map = get_func_map(code)

    not_mutated_code = ""
    for func_name_b in func_map.keys():
        if func_name_b != func_name:
            not_mutated_code += add_iil_holes(func_map[func_name_b]) + "\n\n"
        else:
            not_mutated_code += func_map[func_name_b] + "\n\n"

    ind_clean_line_list = func_map[func_name].split("\n")
    hole_result_code = ""

    for i in range(len(ind_clean_line_list)):
        line = ind_clean_line_list[i]

        if is_method_sign(line):
            hole_result_code += line + "\n"
        elif is_if_stat(line):
            ind = get_indent(line)
            hole_result_code += "".join([" " for j in range(ind)]) + "Holes.vari_hist_hole(locals())\n"
            hole_result_code += line + "\n"
        elif is_elif_stat(line) or \
                is_else_stat(line):
            ind = get_indent(line)
            hole_result_code += line + "\n"
            hole_result_code += "".join([" " for j in range(ind+4)]) + "Holes.vari_hist_hole(locals())\n"
        elif is_for_loop_stat(line) or \
                is_while_loop_stat(line):
            ind = get_indent(line)
            hole_result_code += "".join([" " for j in range(ind)]) + "Holes.vari_hist_hole(locals())\n"
            hole_result_code += line + "\n"
            hole_result_code += "".join([" " for j in range(ind + 4)]) + "Holes.vari_hist_hole(locals())\n"
        else:
            ind = get_indent(line)
            if ind > 0:
                hole_result_code += "".join([" " for k in range(ind)])
                hole_result_code += "Holes.vari_hist_hole(locals())\n"
                hole_result_code += line + "\n"
                hole_result_code += "".join([" " for k in range(ind)])
                hole_result_code += "Holes.vari_hist_hole(locals())\n"
    return not_mutated_code + hole_result_code


def get_hole_dsp_dict(code, ln_list=None):
    line_list = code.split("\n")
    hole_dsp_dict = {}

    # Detect lines that can plant cond_hole or assigne_hole
    sig = ""
    for i in range(len(line_list)):
        line = line_list[i]
        if is_method_sign(line):
            sig = line[line.find("def")+3:line.find("(")].strip()
            continue

        if sig != "" and sig in line:
            continue

        if ln_list is not None and i not in ln_list:
            continue

        hole_dsp_dict[i] = []

        if is_cond_stat(line): # and mut_cf:
            hole_dsp_dict[i].append("cond")
        if is_assign_stat(line) and not has_method_call(line):
            hole_dsp_dict[i].append("assign")

        ind_bnd = get_indent(line)
        for j in range(i - 1, 0, -1):
            line_curr = line_list[j]
            ind_curr = get_indent(line_curr)
            if ind_curr <= ind_bnd:
                if is_loop_stat(line_curr):
                    hole_dsp_dict[i].append("ctn")
                    hole_dsp_dict[i].append("brk")
                    break
                ind_bnd = ind_curr
            else:
                break

        if not is_method_sign(line) and not is_cond_stat(line) and len(line) > 1:
            hole_dsp_dict[i].append("rm")
    return hole_dsp_dict


def add_holes(code, task, ln_list):#vari_set=None
    assert(ln_list is not None and len(ln_list) > 0)
    ln_list = sorted(ln_list)

    sl_map = {}
    old_cond = "True"
    old_assign = "1"
    ind_clean_line_list = code.split("\n")
    hole_result_code = ""
    for i in range(len(ind_clean_line_list)):
        sl_map[i] = 0.01
        line = ind_clean_line_list[i] + "\n"

        if is_method_sign(line):
            hole_result_code += line
            hole_result_code += "    Holes.iil_hole(" + str(i + sl_map[i]) + ")\n" #
            sl_map[i] += 0.01
            continue

        if is_cond_stat(line) and "cond_" + str(i) in task:
            l = 0
            r = 0
            token_list = get_token_list(line)
            for token in token_list:
                if tok_name[token.exact_type] == "NAME":
                    if token.string == "if":
                        l = token.start[1] + 3
                    elif token.string == "elif":
                        l = token.start[1] + 5
                    elif token.string == "while":
                        l = token.start[1] + 6
                elif tok_name[token.exact_type] == "COLON":
                    if token.string == ":":
                        r = token.start[1]
            condition_code = line[l:r]

            condition_code = rm_indent(condition_code.replace("\"", "\\\""))
            hole_result_code += line[:l] + \
                            "Holes.condition_hole(" + str(i) + \
                            ", r\"" + condition_code + "\", " + \
                            "locals()" + "):\n"
            old_cond = condition_code
        elif is_assign_stat(line) and "assign_" + str(i) in task:# and not self.__has_method_call(line):
            l = 0

            token_list = get_token_list(line)
            for k in range(len(token_list)):
                token = token_list[k]
                if tok_name[token.exact_type] in ["EQUAL", "PLUSEQUAL", "MINEQUAL", "STAREQUAL", "SLASHEQUAL"] and \
                        token.string in ["=", "+=","-=", "*=", "/="]:
                    l = token.end[1]
                    break
                elif tok_name[token.exact_type] == "NAME" and \
                        token.string == "return":
                    l = token.end[1]
                    break

            assign_code = line[l:-1]

            assign_code = rm_indent(assign_code.replace("\"", "\\\""))
            hole_result_code += line[:l] + \
                           " Holes.assign_hole(" + str(i) + \
                           ", r\"" + assign_code + "\", " + \
                           "locals()" + ")\n"
            old_cond = assign_code
        elif "rm_" + str(i) in task:
            hole_result_code += ""
        elif "brk_" + str(i) in task:
            ind = get_indent(line)
            ind_space = "".join([" " for k in range(ind)])
            hole_result_code += ind_space + "break" + "\n"
            hole_result_code += line
        elif "ctn_" + str(i) in task:
            ind = get_indent(line)
            ind_space = "".join([" " for k in range(ind)])
            hole_result_code += ind_space + "continue" + "\n"
            hole_result_code += line
        elif "ifbrk_" + str(i) in task:
            ind = get_indent(line)
            ind_space = "".join([" " for k in range(ind)])
            hole_result_code += ind_space + \
                                "if Holes.condition_hole(" + str(i) + \
                                ", r\"" + old_cond + "\", " + \
                                "locals()" + "):\n"
            hole_result_code += ind_space + "    " + "break" + "\n"
            hole_result_code += line
        elif "ifctn_" + str(i) in task:
            ind = get_indent(line)
            ind_space = "".join([" " for k in range(ind)])
            hole_result_code += ind_space + \
                                "if Holes.condition_hole(" + str(i) + \
                                ", r\"" + old_cond + "\", " + \
                                "locals()" + "):\n"
            hole_result_code += ind_space + "    " + "continue" + "\n"
            hole_result_code += line
        elif "ifret_" + str(i) in task:
            ind = get_indent(line)
            ind_space = "".join([" " for k in range(ind)])
            hole_result_code += ind_space + "if " + "Holes.condition_hole(" + str(i + sl_map[i]) + \
                                ", r\"" + old_cond + "\", " + \
                                "locals()" + "):\n"
            sl_map[i] += 0.01
            hole_result_code += ind_space + "    return " + "Holes.assign_hole(" + str(i + sl_map[i]) + \
                                ", r\"" + old_assign + "\", " + \
                                "locals()" + ")\n"
            sl_map[i] += 0.01
            hole_result_code += line
        elif "ret_" + str(i) in task:
            ind = get_indent(line)
            ind_space = "".join([" " for k in range(ind)])


            hole_result_code += ind_space + "return " + "Holes.assign_hole(" + str(i + sl_map[i]) + \
                                ", r\"" + old_assign + "\", " + \
                                "locals()" + ")\n"
            hole_result_code += line
            sl_map[i] += 0.01

        elif "ifcond_" + str(i) in task and not is_cond_stat(line) and not is_loop_stat(line):
            ind = get_indent(line)
            ind_space = "".join([" " for k in range(ind)])
            hole_result_code += ind_space + "if " + "Holes.condition_hole(" + str(i + sl_map[i]) + \
                                ", r\"" + old_cond + "\", " + \
                                "locals()" + "):\n"
            sl_map[i] += 0.01
            hole_result_code += "    " + line
        elif "ini_" + str(i) in task:
            ind = get_indent(line)
            ind_space = "".join([" " for k in range(ind)])
            hole_result_code += ind_space + "Holes.init_hole(" + str(i + sl_map[i]) + ",locals())\n"
            sl_map[i] += 0.01
            hole_result_code += line
        elif "method_" + str(i) in task and has_method_call(line):

            tmp_line = copy.deepcopy(line)
            res_line = ""
            while True:
                p_list = re.findall(r"([\w]+(\.[\w]+)*\([\w,\(\)]*\))", tmp_line)

                match_list = [p[0] for p in p_list]
                if len(match_list) > 0:
                    longest_match = max(match_list, key=len)
                    #m = p.search(tmp_line)
                    l = line.index(longest_match)
                    r = l + len(longest_match)
                    #l, r = m.span()
                    res_line += tmp_line[:l] + "Holes.method_hole(" + str(i + sl_map[i]) + ",r\"" + tmp_line[l:r] + "\",locals())"
                    sl_map[i] += 0.01
                    tmp_line = tmp_line[r:]
                else:
                    res_line += tmp_line
                    hole_result_code += res_line
                    break
        elif any(["indent" == atom.split("_")[0] and atom.split("_")[2] == str(i) for atom in task]):
            for atom in task:
                cell_list = atom.split("_")
                if cell_list[0] == "indent" and cell_list[2] == str(i):
                    ind = int(cell_list[1])
                    ind_space = "".join([" " for k in range(ind)])
                    line_base = rm_indent(line)
                    hole_result_code += ind_space + line_base
        else:
            hole_result_code += line
        # Add loop_hole
        if is_loop_stat(line):
            ind = get_indent(ind_clean_line_list[i])
            hole_result_code += "".join([" " for k in range(ind)]) + "    Holes.iil_hole(" + str(i + sl_map[i]) + ")\n" #
            sl_map[i] += 0.01
    return hole_result_code


def gen_hole_task_list(hole_dsp_dict, k_best=5000):
    dsp_str_dict = {}
    for ln, raw_type_list in hole_dsp_dict.items():
        hole_choice_list = []
        for raw_type in raw_type_list:
            name = raw_type + "_" + str(ln)
            hole_choice_list.append(name)
        dsp_str_dict[ln] = hole_choice_list
    ln_list = list(dsp_str_dict.keys())
    task_list = []
    for r in range(1, len(ln_list) + 1):
        for c in combinations(ln_list, r):
            nested_list = []
            for ln in c:
                if len(nested_list) == 0:
                    for name in dsp_str_dict[ln]:
                        nested_list.append([name])
                else:
                    new_nested_list = []
                    for name_list in nested_list:
                        for name in dsp_str_dict[ln]:
                            new_nested_list.append(name_list + [name])
                    nested_list = new_nested_list

            task_list.extend(nested_list)
            if len(task_list) > 10 * k_best:
                break
        if len(task_list) > 10 * k_best:
            break


    task_list = sorted(task_list, key=functools.cmp_to_key(cmp_task))

    return [[]] + task_list[:k_best]

def cmp_task(task_a, task_b):

    if len(task_a) < len(task_b):
        return -1
    elif len(task_a) > len(task_b):
        return 1
    else:
        sa = get_task_score(task_a)
        sb = get_task_score(task_b)
        if sa < sb:
            return -1
        elif sa > sb:
            return 1
        else:
            return 0


def get_task_score(task):
    score_dict = {"ifbrk": 22,
                  "ifctn": 22,
                  "ifret": 22,
                  "ret": 20,
                  "ini": 20,
                  "assign": 20,
                  "cond": 2,
                  "ifcond": 2,
                  "indent": 2,
                  "rm": 4,
                  "ctn": 1,
                  "brk": 1,
                  "method": 1}

    dd = get_dist_dict(task)
    score = 0
    for name_type, cnt in dd.items():
        score += score_dict[name_type] * cnt
    return score


def get_dist_dict(task):
    dist_dict = {}
    for name in task:
        name_type = name.split("_")[0]
        if name_type not in dist_dict.keys():
            dist_dict[name_type] = 0
        dist_dict[name_type] += 1

    return dist_dict