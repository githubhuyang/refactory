# Developers:   Yang Hu, et al.
# Email:    huyang0905@gmail.com

import ast
import numpy
import Levenshtein
from zss import Node, simple_distance
from basic_framework.cfs import get_func_map
from basic_framework.statement import get_token_list
from fastcache import clru_cache


def multi_func_stru_dist(cfs_map_a, cfs_map_b):
    func_name_set = set(cfs_map_a.keys()).union(set(cfs_map_b.keys()))

    sum_d = 0
    for func_name in func_name_set:
        stru_list_a = []
        if func_name in cfs_map_a.keys():
            _, stru_list_a,_ = cfs_map_a[func_name]

        stru_list_b = []
        if func_name in cfs_map_b.keys():
            _, stru_list_b, _ = cfs_map_b[func_name]

        sum_d += stru_dist(stru_list_a, stru_list_b)
    return sum_d


def stru_dist(stru_list_a, stru_list_b):
    str_stru_a = cpr_stru_list(stru_list_a)
    str_stru_b = cpr_stru_list(stru_list_b)
    return Levenshtein.distance(str_stru_a, str_stru_b)


def cpr_stru_list(stru_list):
    cpr_str = ""
    for stru in stru_list:
        if stru == "bb":
            cpr_str += "b"
        elif stru == "sig":
            cpr_str += "s"
        elif stru == "for":
            cpr_str += "f"
        elif stru == "while":
            cpr_str += "w"
        elif stru == "if":
            cpr_str += "i"
        elif stru == "elif":
            cpr_str += "e"
        elif stru == "else":
            cpr_str += "l"
    return cpr_str


def str_node(node):
    return acc_str_node(node)


# accurate label approach
def acc_str_node(node):
    if hasattr(node, "id"):
        return node.id
    elif hasattr(node, "name"):
        return node.name
    elif hasattr(node, "arg"):
        return node.arg
    elif hasattr(node, "n"):
        return str(node.n)
    elif hasattr(node, "s"):
        return "\'" + node.s + "\'"
    else:
        if node.__class__.__name__ in ["Module", "Load", "Store"]:
            return ""
        else:
            return node.__class__.__name__


def zss_ast_visit(ast_node, parent_zss_node):
    zss_label = str_node(ast_node)
    if zss_label == "":
        for field, value in ast.iter_fields(ast_node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        zss_ast_visit(item, parent_zss_node)
            elif isinstance(value, ast.AST):
                zss_ast_visit(value, parent_zss_node)
    else:
        zss_node = Node(zss_label)
        for field, value in ast.iter_fields(ast_node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        zss_ast_visit(item, zss_node)
            elif isinstance(value, ast.AST):
                zss_ast_visit(value, zss_node)
        parent_zss_node.addkid(zss_node)


def zss_node_cnt(zss_node):
    s = 1
    for child_zss_node in zss_node.children:
        s += zss_node_cnt(child_zss_node)
    return s


def zss_func_ast_size(code):
    root_node = ast.parse(code)
    root_zss_node = Node("root")
    zss_ast_visit(root_node, root_zss_node)
    return zss_node_cnt(root_zss_node)


def zss_ast_size(code):
    s = 0
    func_map = get_func_map(code)
    for func_name, func_code in func_map.items():
        s += zss_func_ast_size(func_code)
    return s



def label_weight(l1, l2):
    if l1 == l2:
        return 0
    else:
        return 1


def zss_code_distance(code_a, code_b):
    root_node_a = ast.parse(code_a)
    root_zss_node_a = Node("root")
    zss_ast_visit(root_node_a, root_zss_node_a)

    root_node_b = ast.parse(code_b)
    root_zss_node_b = Node("root")
    zss_ast_visit(root_node_b, root_zss_node_b)

    return simple_distance(root_zss_node_a, root_zss_node_b, label_dist=label_weight)


@clru_cache(maxsize=1024)
def multi_func_code_distance(code_a, code_b, ted_func):
    func_map_a = get_func_map(code_a)
    func_map_b = get_func_map(code_b)

    func_name_set = set(func_map_a.keys()).union(set(func_map_b.keys()))

    sum_d = 0
    for func_name in func_name_set:
        func_code_a = ""
        if func_name in func_map_a.keys():
            func_code_a = func_map_a[func_name]

        func_code_b = ""
        if func_name in func_map_b.keys():
            func_code_b = func_map_b[func_name]
        sum_d += ted_func(func_code_a, func_code_b)
    return sum_d


def zss_multi_func_code_distance(code_a, code_b):
    return multi_func_code_distance(code_a, code_b, zss_code_distance)


def zss_code_ast_edit(code_a, code_b):
    root_node_a = ast.parse(code_a)
    root_zss_node_a = Node("root")
    zss_ast_visit(root_node_a, root_zss_node_a)

    root_node_b = ast.parse(code_b)
    root_zss_node_b = Node("root")
    zss_ast_visit(root_node_b, root_zss_node_b)

    cost, ops = simple_distance(root_zss_node_a, root_zss_node_b, label_dist=label_weight, return_operations=True)
    return cost, ops


def lev_tl_dist(token_list_a, token_list_b):
    size_x = len(token_list_a) + 1
    size_y = len(token_list_b) + 1
    matrix = numpy.zeros((size_x, size_y))
    for x in range(size_x):
        matrix [x, 0] = x
    for y in range(size_y):
        matrix [0, y] = y

    for x in range(1, size_x):
        for y in range(1, size_y):
            if token_list_a[x-1].string == token_list_b[y-1].string:
                matrix[x,y] = min(
                    matrix[x-1, y] + 1,
                    matrix[x-1, y-1],
                    matrix[x, y-1] + 1
                )
            else:
                matrix[x,y] = min(
                    matrix[x-1,y] + 1,
                    matrix[x-1,y-1] + 1,
                    matrix[x,y-1] + 1
                )
    return matrix[size_x - 1, size_y - 1]


def smt_lev_tl_dist(token_list_a, token_list_b, limit):
    size_x = len(token_list_a) + 1
    size_y = len(token_list_b) + 1
    matrix = numpy.zeros((size_x, size_y))
    for x in range(size_x):
        matrix[x, 0] = x
    for y in range(size_y):
        matrix[0, y] = y

    for x in range(1, size_x):
        for y in range(1, size_y):
            if token_list_a[x - 1].string == token_list_b[y - 1].string:
                matrix[x, y] = min(
                    matrix[x - 1, y] + 1,
                    matrix[x - 1, y - 1],
                    matrix[x, y - 1] + 1
                )
            else:
                matrix[x, y] = min(
                    matrix[x - 1, y] + 1,
                    matrix[x - 1, y - 1] + 1,
                    matrix[x, y - 1] + 1
                )
        if all(matrix[x, y] > limit for y in range(size_y)):
            return limit + 1
    return matrix[size_x - 1, size_y - 1]


def lev_code_distance(func_code_a, func_code_b):
    token_list_a = get_token_list(func_code_a)
    token_list_b = get_token_list(func_code_b)
    return lev_tl_dist(token_list_a, token_list_b)


def lev_multi_func_code_distance(code_a, code_b):
    return multi_func_code_distance(code_a, code_b, lev_code_distance)


def smt_lev_multi_func_code_distance(code_a, code_b, limit):
    token_list_a = get_token_list(code_a)
    token_list_b = get_token_list(code_b)
    return smt_lev_tl_dist(token_list_a, token_list_b, limit)


def apted_ast_visit(ast_node):
    apted_str = ""
    apted_label = str_node(ast_node)
    if apted_label == "":
        for field, value in ast.iter_fields(ast_node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        apted_str += apted_ast_visit(item)
            elif isinstance(value, ast.AST):
                apted_str += apted_ast_visit(value)
    else:
        apted_str += "{" + apted_label
        for field, value in ast.iter_fields(ast_node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        apted_str += apted_ast_visit(item)
            elif isinstance(value, ast.AST):
                apted_str += apted_ast_visit(value)
        apted_str += "}"
    return apted_str


def gen_apted_tree(code):
    from apted.helpers import Tree
    tree_str = apted_ast_visit(ast.parse(code))
    return Tree.from_text(tree_str)


def apted_code_distance(code_a, code_b):
    tree_a = gen_apted_tree(code_a)
    tree_b = gen_apted_tree(code_b)

    from apted import APTED

    apted = APTED(tree_a, tree_b)
    ted = apted.compute_edit_distance()
    return ted


def apted_multi_func_code_distance(code_a, code_b):
    return multi_func_code_distance(code_a, code_b, apted_code_distance)