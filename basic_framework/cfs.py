# Developers:   Yang Hu, et al.
# Email:    huyang0905@gmail.com

from basic_framework.utils import regularize, rm_bb_indent, resume_bb_indent
from basic_framework.statement import *
from fastcache import clru_cache
import random
import copy
import sys


@clru_cache(maxsize=1024)
def get_cfs_map(code):
    func_map = get_func_map(code)

    cfs_map = {}
    for func_name, func_code in func_map.items():
        bb_list, stru_list, indent_list = get_func_cfs(func_code)
        cfs_map[func_name] = (bb_list, stru_list, indent_list)
    return cfs_map


def cfs_map_equal(cfs_map_a, cfs_map_b):
    if set(cfs_map_a.keys()) != set(cfs_map_b.keys()):
        return False

    for cfs_func in cfs_map_a.keys():
        _, stru_list_a, indent_list_a = cfs_map_a[cfs_func]
        _, stru_list_b, indent_list_b = cfs_map_b[cfs_func]
        if stru_list_a != stru_list_b or \
                indent_list_a != indent_list_b:
            return False
    return True


def get_func_map(code):

    class FuncVisitor(ast.NodeVisitor):
        def __init__(self):
            super()
            self.func_map = {}

        def visit_FunctionDef(self, node):
            self.func_map[node.name] = regularize(astunparse.unparse(node))

        def run(self, code):
            n = ast.parse(code)
            self.visit(n)
            return self.func_map

    return FuncVisitor().run(code)


def get_func_cfs(code):
    line_list = code.split("\n")
    block_list = []
    stru_list = []
    indent_list = []
    block_code = ""

    curr_ind = 0
    for line in line_list:
        if "empty_hole" in line or len(line) == 0:
            continue
        if is_method_sign(line):
            block_code = ""
            block_list.append(line + "\n")
            stru_list.append('sig')
            indent_list.append(curr_ind)
            curr_ind += 4
        elif is_if_stat(line):
            block_list.append(block_code)
            stru_list.append('bb')
            indent_list.append(curr_ind)

            line_ind = get_indent(line)
            if curr_ind < line_ind:
                block_list.append("")
                stru_list.append("bb")
                indent_list.append(line_ind)
            elif curr_ind > line_ind:
                for k in range(curr_ind - 4, line_ind - 4, -4):
                    block_list.append("")
                    stru_list.append("bb")
                    indent_list.append(k)

            block_code = ""
            block_list.append(line + "\n")
            stru_list.append('if')
            indent_list.append(line_ind)
            curr_ind = line_ind + 4
        elif is_elif_stat(line):
            block_list.append(block_code)
            stru_list.append('bb')
            indent_list.append(curr_ind)

            line_ind = get_indent(line)
            if curr_ind > line_ind:
                for k in range(curr_ind - 4, line_ind, -4):
                    block_list.append("")
                    stru_list.append("bb")
                    indent_list.append(k)

            block_code = ""
            block_list.append(line + "\n")
            stru_list.append('elif')
            indent_list.append(get_indent(line))
            curr_ind = get_indent(line) + 4
        elif is_else_stat(line):
            block_list.append(block_code)
            stru_list.append('bb')
            indent_list.append(curr_ind)

            line_ind = get_indent(line)
            if curr_ind > line_ind:
                for k in range(curr_ind - 4, line_ind, -4):
                    block_list.append("")
                    stru_list.append("bb")
                    indent_list.append(k)

            block_code = ""
            block_list.append(line + "\n")
            stru_list.append('else')
            indent_list.append(get_indent(line))
            curr_ind = get_indent(line) + 4
        elif is_for_loop_stat(line):
            block_list.append(block_code)
            stru_list.append('bb')
            indent_list.append(curr_ind)

            line_ind = get_indent(line)
            if curr_ind < line_ind:
                block_list.append("")
                stru_list.append("bb")
                indent_list.append(line_ind)
            elif curr_ind > line_ind:
                for k in range(curr_ind - 4, line_ind - 4, -4):
                    block_list.append("")
                    stru_list.append("bb")
                    indent_list.append(k)

            block_code = ""
            block_list.append(line + "\n")
            stru_list.append('for')
            indent_list.append(line_ind)
            curr_ind = line_ind + 4
        elif is_while_loop_stat(line):
            block_list.append(block_code)
            stru_list.append('bb')
            indent_list.append(curr_ind)

            line_ind = get_indent(line)
            if curr_ind < line_ind:
                block_list.append("")
                stru_list.append("bb")
                indent_list.append(line_ind)
            elif curr_ind > line_ind:
                for k in range(curr_ind - 4, line_ind - 4, -4):
                    block_list.append("")
                    stru_list.append("bb")
                    indent_list.append(k)

            block_code = ""
            block_list.append(line + "\n")
            stru_list.append('while')
            indent_list.append(line_ind)
            curr_ind = line_ind + 4
        else:
            ind = get_indent(line)
            if ind == curr_ind:
                block_code += line + "\n"
            elif ind > curr_ind:
                for tmp_ind in range(curr_ind, ind, 4):
                    block_list.append(block_code)
                    stru_list.append('bb')
                    indent_list.append(tmp_ind)
                    block_code = ""
                block_code = line + "\n"
                curr_ind = ind
            else:
                for tmp_ind in range(curr_ind, ind, -4):
                    block_list.append(block_code)
                    stru_list.append('bb')
                    indent_list.append(tmp_ind)
                    block_code = ""
                block_code = line + "\n"
                curr_ind = ind
    if len(block_code) > 0:
        block_list.append(block_code)
        stru_list.append('bb')
        curr_ind = get_indent(block_code.split("\n")[0])
        indent_list.append(curr_ind)
        block_code = ""
        if curr_ind > 4:
            for ind in range(curr_ind - 4, 0, -4):
                block_list.append(block_code)
                block_code = ""
                stru_list.append('bb')
                indent_list.append(ind)

    assert (len(block_list) == len(stru_list) and
            len(block_list) == len(indent_list))
    return block_list, stru_list, indent_list


def cfs_mutation(bug_code, corr_code):
    bug_cfs_map = get_cfs_map(bug_code)
    corr_cfs_map = get_cfs_map(corr_code)

    print("structure mutation")

    rev_bug_func_map = {}

    lose_func_list = []
    from basic_framework.distance import cpr_stru_list
    for func_name in corr_cfs_map.keys():
        corr_bb_list, corr_stru_list, corr_indent_list = corr_cfs_map[func_name]
        corr_stru_str = cpr_stru_list(corr_stru_list)

        if func_name not in bug_cfs_map.keys():
            rev_bug_func_map[func_name] = "".join(corr_bb_list)
            lose_func_list.append(func_name)
        else:
            edit_list = []
            bug_bb_list, bug_stru_list, bug_indent_list = bug_cfs_map[func_name]

            if bug_stru_list == corr_stru_list and \
                    bug_indent_list == corr_indent_list:
                pass
            else:
                bug_stru_str = cpr_stru_list(bug_stru_list)
                import Levenshtein
                edit_list = Levenshtein.editops(bug_stru_str, corr_stru_str)

            insert_map = {}
            del_set = set()
            for edit_op, src_idx, dst_idx in edit_list:
                if edit_op == "replace":
                    bug_bb_list[src_idx] = corr_bb_list[dst_idx]
                elif edit_op == "insert":
                    if src_idx not in insert_map.keys():
                        insert_map[src_idx] = []

                    flt_corr_bb_list = [corr_bb_list[idx] for idx in range(len(corr_stru_list)) if corr_stru_list[idx] == corr_stru_list[dst_idx]]

                    assert(len(flt_corr_bb_list) > 0)
                    sel_corr_bb = random.sample(flt_corr_bb_list, 1)[0]

                    insert_map[src_idx].append(sel_corr_bb)
                elif edit_op == "delete":
                    del_set.add(src_idx)

            new_bug_bb_list = []
            for idx in range(len(bug_bb_list)):
                if idx in insert_map.keys():
                    new_bug_bb_list.extend(insert_map[idx])
                bug_bb = bug_bb_list[idx]
                if idx not in del_set:
                    new_bug_bb_list.append(bug_bb)

            if len(bug_bb_list) in insert_map.keys():
                new_bug_bb_list.extend(insert_map[len(bug_bb_list)])

            assert(len(corr_indent_list) == len(new_bug_bb_list))

            for idx in range(len(corr_indent_list)):
                o_ind_bb, _ = rm_bb_indent(new_bug_bb_list[idx])
                if len(o_ind_bb) == 0:
                    o_ind_bb = "pass\n"

                new_bb = resume_bb_indent(o_ind_bb, corr_indent_list[idx])
                new_bug_bb_list[idx] = new_bb

            rev_bug_func_map[func_name] = "".join(new_bug_bb_list)

    return "\n\n".join(list(rev_bug_func_map.values())), lose_func_list