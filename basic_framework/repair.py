# Developers:   Yang Hu, et al.
# Email:    huyang0905@gmail.com

import sys
import os
import heapq
from shutil import copyfile
import time
import random
import pickle
import gc, time
from fastcache import clru_cache

from basic_framework.holes import Holes
from basic_framework.f1x import *
from basic_framework.feedback import *
from basic_framework.utils import *
from basic_framework.distance import *
from basic_framework.block import *
from basic_framework.cfs import *
from basic_framework.core_testing import Tester
from basic_framework.statement import *
from basic_framework.hole_injection import *
from basic_framework.template import *
from basic_framework.refactoring_ast import astRefactor
from prettytable import PrettyTable


class HeapUnit:
    def __init__(self, rc, bd):
        self.rc = rc
        self.bd = bd
        self.w = len(self.rc.rname.split(",")) + bd

    def __lt__(self, other):
        return self.w < other.w

    def __eq__(self, other):
        return self.w == other.w


class RefactoredCode:
    def __init__(self, corr_code, fname, rname):
        self.corr_code = corr_code
        self.fname = fname # Original correct code file name
        self.rname = rname # Set of rules applied

    def __lt__(self, other):
        return len(self.rname.split(",")) < len(other.rname.split(","))

    def __eq__(self, other):
        return len(self.rname.split(",")) == len(other.rname.split(","))


class ORO:
    """Online Refactoring Only"""
    def __init__(self, ques_dir_path, sr_list, exp_time):
        self.__ques_dir_path = ques_dir_path
        self.__ans_dir_path = ques_dir_path + "/ans"
        self.__code_dir_path = ques_dir_path + "/code"

        self.__sr_list = sr_list
        self.__exp_time = exp_time

    def run(self, timeout=60):
        print("\n\nOnline refactor submissions in " + self.__ques_dir_path.split("/")[-1] + "\n\n")

        buggy_dir_path = self.__code_dir_path + "/wrong"
        buggy_code_map = self.__get_dir_codes(buggy_dir_path)

        rc_map = {}
        corr_code_map = self.__get_dir_codes(self.__ques_dir_path + "/code/correct")
        corr_fn_code_list = list(corr_code_map.items())

        ref_fn_code_list = list(self.__get_dir_codes(self.__ques_dir_path + "/code/reference").items())

        for sr in self.__sr_list:
            sel_corr_fn_code_list = []
            sel_corr_fn_code_list.extend(ref_fn_code_list)

            if sr == 0:
                pass
            elif sr == 100:
                sel_corr_fn_code_list.extend(corr_fn_code_list)
            else:
                sel_corr_fn_code_list.extend(random.sample(corr_fn_code_list,
                                                        int(sr / 100 * len(corr_fn_code_list))))

            rc_map[sr] = {}
            for exp_idx in range(self.__exp_time):
                rc_map[sr][exp_idx] = {}
                for bug_file_name, bug_code in buggy_code_map.items():
                    print(bug_file_name)

                    try:
                        perf_map = {"gcr_time":0, "or_time":0, "code":""}
                        if not syntax_check(bug_code):
                            rc_map[sr][exp_idx][bug_file_name] = perf_map
                            continue

                        # online refactoring
                        sel_fn_code_map = dict(sel_corr_fn_code_list)

                        ol_refactoring_start_time = time.process_time()
                        corr_rc_map = self.astar_ol_rfty(bug_code, sel_fn_code_map)
                        perf_map["or_time"] = time.process_time() - ol_refactoring_start_time

                        gcr_start_time = time.process_time()
                        best_rc = self.astar_get_cls_rc(bug_code,  corr_rc_map)
                        perf_map["gcr_time"] = time.process_time() - gcr_start_time

                        perf_map["code"] = best_rc.corr_code

                        rc_map[sr][exp_idx][bug_file_name] = perf_map

                    except Exception as e:
                        print(str(e), file=sys.stderr)
                        traceback.print_exc(file=sys.stderr)

        import json
        json_path = self.__ques_dir_path + "/oro.json"
        with open(json_path, 'w', encoding="utf-8") as f:
            json.dump(rc_map, f)


    def __get_dir_codes(self, code_dir_path):
        code_map = {}
        for code_file_name in os.listdir(code_dir_path):
            code_path = code_dir_path + "/" + code_file_name

            code = ""
            with open(code_path, "r") as f:
                code += f.read()

            if not syntax_check(code):
                print(code_file_name + ' has syntax errors.')
                continue

            code = regularize(code)

            code_map[code_file_name] = code
        return code_map

    # single function astar refactoring
    def astar_ol_rfty_func(self, bug_func_code, fname_corrFuncCode, max_step=100):
        h = []
        rc_list = []

        bug_cfs_map = get_cfs_map(bug_func_code)

        # build min binary heap
        for fname, corrCode in fname_corrFuncCode.items():
            rc = RefactoredCode(corrCode, fname, "")
            corr_cfs_map = get_cfs_map(corrCode)
            if cfs_map_equal(bug_cfs_map, corr_cfs_map):
                rc_list.append(rc)
            else:
                d = multi_func_stru_dist(bug_cfs_map, corr_cfs_map)
                hu = HeapUnit(rc, d)
                heapq.heappush(h, hu)

        if len(rc_list) > 0:
            return rc_list

        # heuristic-guided search (astar alg.)
        step = 0
        while len(h) > 0 and step < max_step:
            hu = h[0]
            rc = hu.rc
            d = hu.bd
            
            if d == 0:
                break
            else:
                refactor = astRefactor.Refactor(rc.fname, rc.corr_code)
                refactors = astRefactor.applyRules(refactor, untilDepth=1, results=[])

                heapq.heappop(h)
                for refactor in refactors:
                    for rname in refactor.ruleAppls:
                        for refactoredCode in refactor.ruleAppls[rname]:
                            if "    def " in refactoredCode:
                                continue
                            elif "\nif " in refactoredCode:
                                continue
                            corr_cfs_map = get_cfs_map(refactoredCode)
                            n_d = multi_func_stru_dist(bug_cfs_map, corr_cfs_map)
                            if "," in rc.rname:
                                n_d += len(rc.rname.split(","))

                            n_rname = rc.rname
                            if n_rname == "":
                                n_rname = rname
                            else:
                                n_rname += "," + rname

                            n_rc = RefactoredCode(refactoredCode, refactor.fname, n_rname)
                            n_hu = HeapUnit(n_rc, n_d)
                            heapq.heappush(h, n_hu)
                step += 1

        assert (len(h) > 0)

        # collect code candidates
        best_d = h[0].bd
        while len(h) > 0:
            d = h[0].bd
            rc = h[0].rc
            if d == best_d:
                rc_list.append(rc)
                heapq.heappop(h)
            else:
                break
        return rc_list

    def __get_corr_func_list_map(self, corr_code_map):
        corr_func_list_map = {}
        for file_name, corr_code in corr_code_map.items():
            func_code_map = get_func_map(corr_code)

            for func_name in func_code_map.keys():
                func_code = func_code_map[func_name]
                if func_name not in corr_func_list_map.keys():
                    corr_func_list_map[func_name] = []
                corr_func_list_map[func_name].append((file_name, func_code))

        max_len = max([len(corr_func_list_map[func_name]) for func_name in corr_func_list_map.keys()])
        del_func_name_list = []
        for func_name in corr_func_list_map.keys():
            if max_len - len(corr_func_list_map[func_name]) > 5:
                del_func_name_list.append(func_name)

        for func_name in del_func_name_list:
            del corr_func_list_map[func_name]

        return corr_func_list_map

    def astar_ol_rfty(self, bug_code, fname_corrCode, max_step=100):
        # extract func definition from bug code
        bug_func_map = get_func_map(bug_code)
        corr_func_list_map = self.__get_corr_func_list_map(fname_corrCode)

        rc_list_map = {}
        for func_name, bug_func_code in bug_func_map.items():
            corr_func_code_map = dict(corr_func_list_map[func_name])
            rc_list = self.astar_ol_rfty_func(bug_func_code, corr_func_code_map, max_step)
            rc_list_map[func_name] = rc_list

        return rc_list_map

    def astar_get_cls_rc(self, bug_code, rc_list_map):
        bug_func_map = get_func_map(bug_code)

        code_map = {}
        file_map = {}
        rule_map = {}
        for func_name, bug_func_code in bug_func_map.items():
            func_rc_list = rc_list_map[func_name]
            best_func_rc = self.astar_get_cls_func_rc(bug_func_code, func_rc_list)

            code_map[func_name] = best_func_rc.corr_code
            file_map[func_name] = best_func_rc.fname
            rule_map[func_name] = best_func_rc.rname

        final_corr_code = "\n\n".join(code_map.values())
        final_fname = str(file_map)
        final_rule = str(rule_map)
        best_rc = RefactoredCode(final_corr_code, final_fname, final_rule)

        return best_rc

    def astar_get_cls_func_rc(self, bug_func_code, rc_list):
        # choose best one based on ted
        min_ted, best_rc = None, None
        for rc in rc_list:
            if min_ted is None:
                min_ted = lev_multi_func_code_distance(bug_func_code, rc.corr_code)
                best_rc = rc
            else:
                ted = smt_lev_multi_func_code_distance(bug_func_code, rc.corr_code, min_ted)
                if ted < min_ted:
                    min_ted = ted
                    best_rc = rc
        return best_rc


class BlockRepair:
    def __init__(self, ques_dir_path, is_offline_ref, is_online_ref, is_mutation, sr_list, exp_time):
        self.__ques_dir_path = ques_dir_path
        self.__ans_dir_path = ques_dir_path + "/ans"
        self.__code_dir_path = ques_dir_path + "/code"

        self.__pickle_dir_path = self.__code_dir_path + "/refactor"
        self.__sr_list = sr_list
        self.__exp_time = exp_time

        self.__tester = Tester(ques_dir_path)

        self.__is_offline_ref = is_offline_ref
        self.__is_online_ref = is_online_ref
        self.__is_mutation = is_mutation

    def __get_corr_func_list_map(self, corr_code_map):
        corr_func_list_map = {}
        for file_name, corr_code in corr_code_map.items():
            func_code_map = get_func_map(corr_code)

            for func_name in func_code_map.keys():
                func_code = func_code_map[func_name]
                if func_name not in corr_func_list_map.keys():
                    corr_func_list_map[func_name] = []
                corr_func_list_map[func_name].append((file_name, func_code))

        max_len = max([len(corr_func_list_map[func_name]) for func_name in corr_func_list_map.keys()])
        del_func_name_list = []
        for func_name in corr_func_list_map.keys():
            if max_len - len(corr_func_list_map[func_name]) > 5:
                del_func_name_list.append(func_name)

        for func_name in del_func_name_list:
            del corr_func_list_map[func_name]

        return corr_func_list_map

    def __filter_corr_codes(self, corr_code_map):
        corr_func_list_map = self.__get_corr_func_list_map(corr_code_map)

        new_corr_code_map = {}
        for file_name, corr_code in corr_code_map.items():
            func_code_map = get_func_map(corr_code)

            is_rm = False
            for func_name in func_code_map.keys():
                #func_code = func_code_map[func_name]
                if func_name not in corr_func_list_map.keys():
                    is_rm = True
                    break

            if not is_rm:
                new_corr_code_map[file_name] = corr_code
        return corr_code_map

    def __get_trace_map(self, bug_code, func_name):
        trace_map = {}

        bug_hole_code = add_vari_hist_holes(bug_code, func_name)

        tc_id_list = self.__tester.get_tc_id_list()
        for tc_id in tc_id_list:
            Holes.init_global_vars()
            Holes.vari_hist = {}
            self.__tester.run_tc(bug_hole_code, tc_id, timeout=1)

            trace_map[tc_id] = Holes.vari_hist
        return trace_map

    def __is_equal(self, object_a, object_b):
        if str(type(object_a)) == str(type(object_b)):
            if object_a == object_b:
                return True
            else:
                return False
        else:
            close_type_list = ["<class 'list'>", "<class 'tuple'>"]
            if str(type(object_a)) in close_type_list and \
                    str(type(object_b)) in close_type_list:
                if list(object_a) == list(object_b):
                    return True
                else:
                    return False
            else:
                return False

    def __is_hist_equal(self, hist_a, hist_b):
        if len(hist_a) != len(hist_b):
            return False
        for i in range(len(hist_a)):
            if not self.__is_equal(hist_a[i], hist_b[i]):
                return False
        return True

    def __def_use_analysis(self, bb_list, stat_vari_names):
        def_map = {}
        use_map = {}
        for bb_idx in range(len(bb_list)):
            bb = bb_list[bb_idx]
            line_list = bb.split("\n")[:-1]
            for line in line_list:
                token_list = get_token_list(line)

                assign_idx = -1
                for i in range(len(token_list)):
                    token = token_list[i]
                    if token.string in ["=", "+=", "-=", "*=", "/="]:
                        assign_idx = i
                        break

                for i in range(len(token_list)):
                    token = token_list[i]
                    if token.string in stat_vari_names:
                        if i < assign_idx:
                            if token.string not in def_map.keys():
                                def_map[token.string] = set()
                            def_map[token.string].add(bb_idx)
                        elif i > assign_idx:
                            if token.string not in use_map.keys():
                                use_map[token.string] = set()
                            use_map[token.string].add(bb_idx)
        return def_map, use_map

    def __get_func_vns(self, code, func_name):
        func_map = get_func_map(code)
        return get_vari_names(func_map[func_name])

    def get_vn_map(self, bug_code, corr_code, func_name):
        bug_bb_list, bug_stru_list, _ = get_cfs_map(bug_code)[func_name]
        bug_trace_map = self.__get_trace_map(bug_code, func_name)
        bug_vn_list = self.__get_func_vns(bug_code, func_name)

        corr_bb_list, corr_stru_list, _ = get_cfs_map(corr_code)[func_name]
        corr_trace_map = self.__get_trace_map(corr_code, func_name)
        corr_vn_list = self.__get_func_vns(corr_code, func_name)

        base_map = self.__get_vn_map_core(bug_trace_map, corr_trace_map,
                                     bug_bb_list, corr_bb_list,
                                     bug_stru_list, corr_stru_list,
                                     bug_vn_list, corr_vn_list)

        vn_map = {}
        for vn_a, cand_list in base_map.items():
            if len(cand_list) == 0:
                vn_map[vn_a] = cand_list[0]
            else:
                vn_map[vn_a] = random.sample(cand_list, 1)[0]

        return vn_map

    def __get_vn_map_core(self, trace_map_a, trace_map_b,
                        bb_list_a, bb_list_b,
                        stru_list_a, stru_list_b,
                        vari_names_a, vari_names_b):
        tc_id_list = self.__tester.get_tc_id_list()

        base_map = {}

        # Map variables in method signature
        assert(stru_list_a[0]=="sig" and stru_list_b[0]=="sig")
        vari_sig_list_a = get_vari_in_sig(bb_list_a[0])
        vari_sig_list_b = get_vari_in_sig(bb_list_b[0])

        assert(len(vari_sig_list_a) == len(vari_sig_list_b))

        for i in range(len(vari_sig_list_a)):
            base_map[vari_sig_list_a[i]] = [vari_sig_list_b[i]]

        # Map variables based on dynamic equivalence analysis
        vn_set_a = set()
        for tc_id in tc_id_list:
            for vn in trace_map_a[tc_id].keys():
                vn_set_a.add(vn)

        vn_set_b = set()
        for tc_id in tc_id_list:
            for vn in trace_map_b[tc_id].keys():
                vn_set_b.add(vn)

        for vn_a in vn_set_a:
            for vn_b in vn_set_b:
                is_matched = True
                for tc_id in tc_id_list:
                    a_in = vn_a in trace_map_a[tc_id].keys()
                    b_in = vn_b in trace_map_b[tc_id].keys()
                    if not a_in and not b_in:
                        continue
                    elif a_in and not b_in:
                        is_matched = False
                        break
                    elif not a_in and b_in:
                        is_matched = False
                        break
                    else:
                        a_trace_list = trace_map_a[tc_id][vn_a]
                        b_trace_list = trace_map_b[tc_id][vn_b]
                        if not self.__is_hist_equal(a_trace_list, b_trace_list):
                            is_matched = False
                            break
                if is_matched:
                    if vn_a not in base_map.keys():
                        base_map[vn_a] = []
                    base_map[vn_a].append(vn_b)

        # Map variables based on def-use analysis
        def_map_a, use_map_a = self.__def_use_analysis(bb_list_a, vari_names_a)
        def_map_b, use_map_b = self.__def_use_analysis(bb_list_b, vari_names_b)
        for vn_a in vari_names_a:
            for vn_b in vari_names_b:
                if vn_a not in base_map.keys() and \
                    vn_b not in self.get_mapped_vari(base_map):
                    if vn_a in def_map_a.keys() and vn_b in def_map_b.keys():
                        if def_map_a[vn_a] == def_map_b[vn_b]:
                            if vn_a not in base_map.keys():
                                base_map[vn_a] = []
                            base_map[vn_a].append(vn_b)
                    elif vn_a in use_map_a.keys() and vn_b in use_map_b.keys():
                        if use_map_a[vn_a] == use_map_b[vn_b]:
                            if vn_a not in base_map.keys():
                                base_map[vn_a] = []
                            base_map[vn_a].append(vn_b)

        # Using close name str to map variables
        for vn_a in vari_names_a:
            for vn_b in vari_names_b:
                if vn_a not in base_map.keys() and \
                    vn_b not in self.get_mapped_vari(base_map) and \
                    vn_a == vn_b:
                    if vn_a not in base_map.keys():
                        base_map[vn_a] = []
                    base_map[vn_a].append(vn_b)

        # Process residual variables
        for bvn in vari_names_a:
            if bvn not in base_map.keys():
                base_map[bvn] = ["buggy_" + bvn]

        for cvn in vari_names_b:
            if cvn not in self.get_mapped_vari(base_map):
                base_map["ref_" + cvn] = [cvn]

        return base_map

    def get_mapped_vari(self, base_map):
        mapped_vari_list = []
        for cand_list in base_map.values():
            mapped_vari_list.extend(cand_list)
        return set(mapped_vari_list)

    def __swt_bb_vn(self, bb_list, bb_idx, vn_map):
        func_code = "".join(bb_list)
        swt_func_code = swt_func_vn(func_code, vn_map)
        bb_list, _, _ = get_func_cfs(swt_func_code)
        return bb_list[bb_idx]

    def synthesize(self, code, timeout):
        start_time = time.process_time()

        Holes.init_global_vars()
        Holes.ssl = SearchSpaceList()
        Holes.ssl.add_ss(SearchSpace())

        tc_id_list = self.__tester.get_tc_id_list()

        for tc_id in tc_id_list:
            left_timeout = timeout - (time.process_time() - start_time)
            if left_timeout < 0:
                break

            Holes.ter = TERelation()
            Holes.curr_tc_id = tc_id

            ssl_new = SearchSpaceList()
            ss_list = Holes.ssl.get_ss_list()

            for curr_ss in ss_list:
                left_timeout = timeout - (time.process_time() - start_time)
                if left_timeout < 0:
                    break

                Holes.curr_ss = curr_ss
                Holes.curr_eg.clear()

                while True:
                    Holes.ldt_dict = {}

                    left_timeout = timeout - (time.process_time() - start_time)
                    if left_timeout < 0:
                        break

                    real_output, exp_output = self.__tester.run_tc(code, tc_id, left_timeout)


                    if real_output == exp_output:
                        ss = SearchSpace()
                        expr_rec_dict = Holes.curr_eg.get_expr_rec_dict()
                        for ln in expr_rec_dict.keys():
                            times_list = list(expr_rec_dict[ln].keys())
                            min_times = numpy.min(times_list)
                            expr_rec = expr_rec_dict[ln][min_times]
                            ss.add_expr_list_ws(ln, expr_rec.repr_expr_list, expr_rec.repr_score_list)
                        if not ssl_new.is_contain(ss):
                            ssl_new.add_ss(ss)

                    is_continue = Holes.curr_eg.next()
                    if not is_continue:
                        break

            comb_ssl = SearchSpaceList()
            for ss_a in Holes.ssl.ss_list:
                for ss_b in ssl_new.ss_list:
                    comb_s = SearchSpace()
                    for ln in ss_b.ss_dict.keys():
                        comb_s.ss_dict[ln] = ss_b.ss_dict[ln]
                        comb_s.score_dict[ln] = ss_b.score_dict[ln]
                    for ln in ss_a.ss_dict.keys():
                        if ln not in ss_b.ss_dict.keys():
                            comb_s.ss_dict[ln] = ss_a.ss_dict[ln]
                            comb_s.score_dict[ln] = ss_a.score_dict[ln]
                    if not comb_ssl.is_contain(comb_s):
                        comb_ssl.add_ss(comb_s)

            Holes.ssl = comb_ssl

        return Holes.ssl.ss_list, Holes.in_genhole_time

    def rep_bug_code(self, bug_code, corr_code, temp_list, const_list, rep_perf_map, timeout=60.0):

        start_time = time.process_time()

        Holes.template_list = temp_list
        Holes.constant_list = const_list

        rep_func_map = {}

        rep_perf_map["corr_code"] = corr_code
        rep_perf_map["ori_bug_code"] = bug_code
        rep_perf_map["bug_ast_size"] = zss_ast_size(rep_perf_map["ori_bug_code"])

        is_mutate = False
        lose_func_list = []
        if not cfs_map_equal(get_cfs_map(bug_code), get_cfs_map(corr_code)):
            rep_perf_map["match"] = 0
            if self.__is_mutation:
                # 1.2 structure mutation
                mut_start_time = time.process_time()
                bug_code, lose_func_list = cfs_mutation(bug_code, corr_code)
                rep_perf_map["mut_time"] = time.process_time() - mut_start_time
                is_mutate = True
            else:
                rep_perf_map["status"] = "fail_no_match"
                rep_perf_map["mut_time"] = "N/A"
                return
        else:
            rep_perf_map["match"] = 1
            rep_perf_map["mut_time"] = 0

        rep_perf_map["align_bug_code"] = bug_code

        # 2. block mapping
        bb_map_start_time = time.process_time()
        bug_cfs_map = get_cfs_map(bug_code)
        corr_cfs_map = get_cfs_map(corr_code)
        # after doing alignment, structure should be the same
        assert(cfs_map_equal(bug_cfs_map, corr_cfs_map))
        rep_perf_map["bb_map_time"] = time.process_time() - bb_map_start_time

        # 3. variable mapping, spec. generation and patch synthesis
        rep_perf_map["vn_map_time"] = 0
        rep_perf_map["spec_syn_time"] = 0
        rep_perf_map["spec_time"] = 0
        rep_perf_map["syn_time"] = 0

        is_timeout = False

        rep_perf_map["vn_map"] = {}
        for func_name in corr_cfs_map.keys():
            left_timeout = timeout - (time.process_time() - start_time)
            if left_timeout < 0:
                is_timeout = True
                break

            if func_name in lose_func_list:
                continue

            corr_bb_list, corr_stru_list, corr_indent_list = corr_cfs_map[func_name]

            bug_func_map = get_func_map(bug_code)
            tmp_func_map = get_func_map(corr_code)

            del tmp_func_map[func_name]
            icpl_corr_code = "\n\n".join(list(tmp_func_map.values()))
            tmp_func_map[func_name] = bug_func_map[func_name]
            rev_bug_code = "\n\n".join(list(tmp_func_map.values()))

            bug_cfs_map = get_cfs_map(rev_bug_code)
            bug_bb_list, bug_stru_list, bug_indent_list = bug_cfs_map[func_name]

            # 3.1 variable mapping
            vn_map_start_time = time.process_time()
            base_map = self.get_vn_map(rev_bug_code, corr_code, func_name)

            reverse_map = {}
            for k, v in base_map.items():
                reverse_map[v] = k

            rep_perf_map["vn_map_time"] += (time.process_time() - vn_map_start_time)
            rep_perf_map["vn_map"][func_name] = base_map

            # 3.2 spec. & rep.
            spec_syn_start_time = time.process_time()
            vn_map_list = [base_map]
            for vn_map in vn_map_list:
                left_timeout = timeout - (time.process_time() - start_time)
                if left_timeout < 0:
                    is_timeout = True
                    break

                vn_map_success = True
                rev_vn_map = {}
                for key, value in vn_map.items():
                    rev_vn_map[value] = key

                wait_rep_bb_list = copy.deepcopy(bug_bb_list)
                for k in range(len(corr_stru_list)):
                    left_timeout = timeout - (time.process_time() - start_time)
                    if left_timeout < 0:
                        is_timeout = True
                        break

                    swt_bb_list = copy.deepcopy(corr_bb_list)
                    if corr_stru_list[k] == "sig":
                        wait_rep_bb_list[k] = self.__swt_bb_vn(corr_bb_list, k, rev_vn_map)
                    elif corr_stru_list[k] in ["bb", "if", "elif", "while", "for"]:

                        if is_empty_block(bug_bb_list[k]) and is_empty_block(corr_bb_list[k]):
                            pass
                        elif is_empty_block(bug_bb_list[k]) and not is_empty_block(corr_bb_list[k]):
                            wait_rep_bb_list[k] = self.__swt_bb_vn(corr_bb_list, k, rev_vn_map)
                        elif (not is_empty_block(bug_bb_list[k])) and is_empty_block(corr_bb_list[k]):
                            wait_rep_bb_list[k] = corr_bb_list[k]
                        else:
                            if "if True:" in corr_bb_list[k] or "elif True:" in corr_bb_list[k]:
                                wait_rep_bb_list[k] = corr_bb_list[k]
                            elif bug_stru_list[k] in ["for"]:#, "while"
                                wait_rep_bb_list[k] = self.__swt_bb_vn(corr_bb_list, k, rev_vn_map)
                            else:
                                swt_bb_list[k] = self.__swt_bb_vn(bug_bb_list, k, vn_map)

                                if swt_bb_list[k] != corr_bb_list[k]:
                                    swt_code = "".join(swt_bb_list)
                                    holed_swt_code = add_iil_holes(swt_code)

                                    tr_dict = self.__tester.tv_code(icpl_corr_code + "\n\n" + holed_swt_code, timeout=2)

                                    if self.__tester.is_pass(tr_dict):
                                        corr_bb_list[k] = swt_bb_list[k]
                                        wait_rep_bb_list[k] = self.__swt_bb_vn(swt_bb_list, k,rev_vn_map)

                                    else:
                                        # synthesis
                                        assert (k != 0)
                                        ln_start = 0
                                        for b_index in range(k):
                                            ln_start += swt_bb_list[b_index].count("\n")
                                        ln_end = ln_start + swt_bb_list[k].count("\n")

                                        bb_ln_list = list(range(ln_start, ln_end))


                                        hole_dsp_dict = get_hole_dsp_dict(swt_code, ln_list=bb_ln_list)
                                        task_list = gen_hole_task_list(hole_dsp_dict)

                                        #huyang
                                        block_success = False

                                        for task in task_list:
                                            Holes.init_global_vars()
                                            gc.collect()

                                            holed_swt_code = add_holes(swt_code, task, bb_ln_list)

                                            left_timeout = timeout - (time.process_time() - start_time)
                                            if left_timeout < 0:
                                                wait_rep_bb_list[k] = self.__swt_bb_vn(corr_bb_list, k, rev_vn_map)
                                                is_timeout = True
                                                break

                                            the_code = ""
                                            if len(icpl_corr_code) != 0:
                                                the_code = icpl_corr_code+"\n\n"+holed_swt_code
                                            else:
                                                the_code = holed_swt_code

                                            syn_start_time = time.process_time()

                                            repair_dict_list, inhole_time = self.synthesize(the_code, left_timeout/len(corr_stru_list))
                                           
                                            rep_perf_map["syn_time"] += time.process_time() - syn_start_time#inhole_time

                                            if len(repair_dict_list) > 0:
                                                func_rep_code = gen_rep_code(repair_dict_list, holed_swt_code)

                                                holed_func_rep_code = add_iil_holes(func_rep_code)

                                                tr_dict = self.__tester.tv_code(icpl_corr_code + "\n\n" + holed_func_rep_code)
                                                if self.__tester.is_pass(tr_dict):
                                                    block_success = True
                                                    rep_bb_list, rep_stru_list, rep_indent_list = get_func_cfs(func_rep_code)

                                                    if len(rep_bb_list) == 0:
                                                        wait_rep_bb_list[k] = self.__swt_bb_vn(corr_bb_list, k, rev_vn_map)
                                                    else:
                                                        wait_rep_bb_list[k] = self.__swt_bb_vn(rep_bb_list, k, rev_vn_map)
                                                    break


                                        if not block_success:
                                            wait_rep_bb_list[k] = self.__swt_bb_vn(corr_bb_list, k, rev_vn_map)

                                else:
                                    wait_rep_bb_list[k] = self.__swt_bb_vn(corr_bb_list, k, rev_vn_map)

                if vn_map_success:
                    rep_code_cand = "".join(wait_rep_bb_list)

                    tr_dict = self.__tester.tv_code(icpl_corr_code+"\n\n"+rep_code_cand, timeout=2)

                    if self.__tester.is_pass(tr_dict):
                        rep_func_map[func_name] = (rep_code_cand, tr_dict)
                        break
                    else:
                        if func_name not in rep_func_map.keys():
                            rep_func_map[func_name] = (rep_code_cand, tr_dict)
                        else:
                            _, old_tr_dict = rep_func_map[func_name]
                            if list(old_tr_dict.values()).count(True) <  list(tr_dict.values()).count(True):
                                rep_func_map[func_name] = (rep_code_cand, tr_dict)

            rep_perf_map["spec_syn_time"] += (time.process_time() - spec_syn_start_time)

        rep_perf_map["spec_time"] = rep_perf_map["spec_syn_time"] - rep_perf_map["syn_time"]

        func_code_list = []
        for func_name in rep_func_map.keys():
            rep_code_cand, _ = rep_func_map[func_name]
            func_code_list.append(rep_code_cand)

        final_rep_code = "\n\n".join(func_code_list)
        rep_perf_map["rep_code"] = final_rep_code

        tr_dict = self.__tester.tv_code(final_rep_code)
        rep_perf_map["tr"] = tr_dict
        if self.__tester.is_pass(tr_dict):
            if is_mutate:
                rep_perf_map["status"] = "success_w_mut"
            else:
                rep_perf_map["status"] = "success_wo_mut"
        else:
            if is_timeout:
                rep_perf_map["status"] = "fail_timeout"
            else:
                rep_perf_map["status"] = "fail_other"

    def __get_dir_codes(self, code_dir_path):
        code_map = {}
        for code_file_name in os.listdir(code_dir_path):
            code_path = code_dir_path + "/" + code_file_name

            code = ""
            with open(code_path, "r") as f:
                code += f.read()

            if not syntax_check(code):
                print(code_file_name + ' has syntax errors.')
                continue

            code = regularize(code)

            code_map[code_file_name] = code
        return code_map

    # single function astar refactoring
    def astar_ol_rfty_func(self, bug_func_code, fname_corrFuncCode, max_step=100):
        h = []
        rc_list = []

        bug_cfs_map = get_cfs_map(bug_func_code)

        # build min binary heap
        for fname, corrCode in fname_corrFuncCode.items():
            rc = RefactoredCode(corrCode, fname, "")
            corr_cfs_map = get_cfs_map(corrCode)
            if cfs_map_equal(bug_cfs_map, corr_cfs_map):
                rc_list.append(rc)
            else:
                d = multi_func_stru_dist(bug_cfs_map, corr_cfs_map)
                hu = HeapUnit(rc, d)
                heapq.heappush(h, hu)

        if len(rc_list) > 0:
            return rc_list

        # heuristic-guided search (astar alg.)
        step = 0
        while len(h) > 0 and step < max_step:
            hu = h[0]
            rc = hu.rc
            d = hu.bd

            if d == 0:
                break
            else:
                refactor = astRefactor.Refactor(rc.fname, rc.corr_code)
                refactors = astRefactor.applyRules(refactor, untilDepth=1, results=[])

                heapq.heappop(h)
                for refactor in refactors:
                    for rname in refactor.ruleAppls:
                        for refactoredCode in refactor.ruleAppls[rname]:
                            if "    def " in refactoredCode:
                                continue
                            elif "\nif " in refactoredCode:
                                continue
                            corr_cfs_map = get_cfs_map(refactoredCode)
                            n_d = multi_func_stru_dist(bug_cfs_map, corr_cfs_map)
                            if "," in rc.rname:
                                n_d += len(rc.rname.split(",")) # add previous refactoring times

                            n_rname = rc.rname
                            if n_rname == "":
                                n_rname = rname
                            else:
                                n_rname += "," + rname

                            n_rc = RefactoredCode(refactoredCode, refactor.fname, n_rname)
                            n_hu = HeapUnit(n_rc, n_d)
                            heapq.heappush(h, n_hu)
                step += 1

        assert (len(h) > 0)

        # collect code candidates
        best_d = h[0].bd
        while len(h) > 0:
            d = h[0].bd
            rc = h[0].rc
            if d == best_d:
                rc_list.append(rc)
                heapq.heappop(h)
            else:
                break
        return rc_list

    def astar_ol_rfty(self, bug_code, fname_corrCode, max_step=100):
        # extract func definition from bug code
        bug_func_map = get_func_map(bug_code)
        corr_func_list_map = self.__get_corr_func_list_map(fname_corrCode)

        rc_list_map = {}
        for func_name, bug_func_code in bug_func_map.items():
            corr_func_code_map = dict(corr_func_list_map[func_name])
            rc_list = self.astar_ol_rfty_func(bug_func_code, corr_func_code_map, max_step)
            rc_list_map[func_name] = rc_list

        return rc_list_map

    def astar_get_cls_rc(self, bug_code, rc_list_map):
        bug_func_map = get_func_map(bug_code)

        code_map = {}
        file_map = {}
        rule_map = {}
        for func_name, bug_func_code in bug_func_map.items():
            func_rc_list = rc_list_map[func_name]
            best_func_rc = self.astar_get_cls_func_rc(bug_func_code, func_rc_list)

            code_map[func_name] = best_func_rc.corr_code
            file_map[func_name] = best_func_rc.fname
            rule_map[func_name] = best_func_rc.rname

        final_corr_code = "\n\n".join(code_map.values())
        final_fname = str(file_map)
        final_rule = str(rule_map)
        best_rc = RefactoredCode(final_corr_code, final_fname, final_rule)

        return best_rc

    def astar_get_cls_func_rc(self, bug_func_code, rc_list):
        # choose best one based on ted
        min_ted, best_rc = None, None
        for rc in rc_list:
            if min_ted is None:
                min_ted = lev_multi_func_code_distance(bug_func_code, rc.corr_code)
                best_rc = rc
            else:
                ted = smt_lev_multi_func_code_distance(bug_func_code, rc.corr_code, min_ted)
                if ted < min_ted:
                    min_ted = ted
                    best_rc = rc
        return best_rc

    def ol_refactoring(self, bug_code, fname_corrCode):
        refactors = []
        for fname, corrCode in fname_corrCode.items():
            refactor = astRefactor.Refactor(fname, corrCode)
            refactors += astRefactor.applyRules(refactor, untilDepth=1, results=[])

        debug_test = False

        refactoredCodes = []
        for fname, corrCode in fname_corrCode.items():
            refactoredCodes.append(RefactoredCode(corrCode, fname, "ori"))

        for refactor in refactors:
            for rname in refactor.ruleAppls:
                for refactoredCode in refactor.ruleAppls[rname]:
                    if "    def " in refactoredCode:
                        continue
                    elif "\nif " in refactoredCode:
                        continue
                    rc = RefactoredCode(refactoredCode, refactor.fname, rname)
                    if debug_test:
                        tr = self.__tester.tv_code(refactoredCode)
                        if self.__tester.is_pass(tr):
                            refactoredCodes.append(rc)
                        else:
                            print(rname)
                            print("\n")
                            print(tr)
                            print("\n")
                            print(refactoredCode)
                    else:
                        refactoredCodes.append(rc)

        return refactoredCodes


    def get_closest_rc(self, bug_code, refactoredCodes):
        code_map = {}
        fn_map = {}
        rule_map = {}

        i = 0
        for rc in refactoredCodes:
            if "    def " in rc.corr_code:
                continue
            elif "\nif " in rc.corr_code:
                continue

            rc.corr_code = regularize(rc.corr_code)
            code_map["pseudo_"+str(i)] = rc.corr_code
            fn_map[rc.corr_code] = rc.fname
            rule_map[rc.corr_code] = rc.rname
            i += 1

        from basic_framework.refactoring import Refactoring
        rft = Refactoring(code_map, None, 0, None)
        cluster_list_map = rft.ofl_bfs()

        debug_flag = False
        if debug_flag:
            from basic_framework.refactoring import Reporter
            buggy_code_list = list(self.__get_dir_codes(self.__code_dir_path + "/wrong").values())
            reporter = Reporter(buggy_code_list)
            mr = reporter.get_matching_rate(cluster_list_map)
            print("%.4f" % mr)

        sel_code, rules_map, root_file_map = self.sel_corr_code(bug_code, cluster_list_map)

        fn = str(root_file_map)
        if sel_code in fn_map.keys():
            fn = fn_map[sel_code]

        rn = str(rules_map)
        if sel_code in rule_map.keys():
            rn = rule_map[sel_code]

        return RefactoredCode(sel_code, fn, rn)

    def get_closestRefactor(self, bug_code, refactoredCodes):
        # Calculate the closest refactored code        
        bug_map = get_cfs_map(bug_code)
        matchingDist, matchingRefactor = None, None
        nonMatchingDist, nonMatchingRefactor = None, None

        # For each refactored code
        for refactoredCode in refactoredCodes:
            corr_code = refactoredCode.corr_code
            refactor_map = get_cfs_map(corr_code)

            # If control flows are exactly the same
            if cfs_map_equal(bug_map, refactor_map):
                dist = 0
                if matchingDist is None:
                    dist = lev_multi_func_code_distance(bug_code, corr_code)
                else:
                    dist = smt_lev_multi_func_code_distance(bug_code, corr_code, matchingDist)

                if matchingDist is None or dist < matchingDist:
                    matchingDist = dist
                    matchingRefactor = refactoredCode

            else:
                dist = 0
                if nonMatchingDist is None:
                    dist = lev_multi_func_code_distance(bug_code, corr_code)
                else:
                    dist = smt_lev_multi_func_code_distance(bug_code, corr_code, nonMatchingDist)

                if nonMatchingDist is None or dist < nonMatchingDist:
                    nonMatchingDist = dist
                    nonMatchingRefactor = refactoredCode

        closestRefactor = nonMatchingRefactor
        if matchingRefactor is not None:
            closestRefactor = matchingRefactor
        return closestRefactor


    def print_ques_perf(self, sr, exp_idx, status_list, time_list, rps_list):
        try:

            print("\nSummary for " + \
                  self.__ques_dir_path.split("/")[-1] + \
                  " (sampling_rate = " + str(sr) + "%, exp_idx = " + str(exp_idx) + ")")

            pt = PrettyTable()
            pt.field_names = ["Metric", "Value"]
            c_success = status_list.count("success_wo_mut") + status_list.count("success_w_mut")
            c_success_wo_mut = status_list.count("success_wo_mut")

            pt.add_row(["rep_rate", "%.3f" % (c_success / len(status_list))])
            pt.add_row(["rep_rate_wo_mut", "%.3f" % (c_success_wo_mut / len(status_list))])

            if c_success > 0:
                pt.add_row(["time_cost", "%.3f" % numpy.mean(time_list)])
                pt.add_row(["rps", "%.3f" % numpy.mean(rps_list)])
            print(pt.get_string())
        except Exception as e:
            print("print_ques_perf failed!", self.__ques_dir_path.split("/")[-1])
            print(str(e))
            print("\n")

    def print_perf(self, bug_file_name, code_perf_map):
        try:
            pt = PrettyTable()
            print(code_perf_map["status"])
            pt.field_names = ["Metric", "Value"]

            if "success" in code_perf_map["status"]:
                pt.add_row(["time", "%.3f" % code_perf_map["total_time"]])

                if self.__is_offline_ref:
                    pt.add_row(["stru_match_time", "%.3f" % code_perf_map["stru_match_time"]])
                else:
                    pt.add_row(["ol_refactoring_time", "%.3f" % code_perf_map["ol_refactoring_time"]])
                    pt.add_row(["gcr_time", "%.3f" % code_perf_map["gcr_time"]])
                    

                pt.add_row(["mut_time", "%.3f" % code_perf_map["mut_time"]])
                pt.add_row(["vn_map_time", "%.3f" % code_perf_map["vn_map_time"]])
                pt.add_row(["spec_syn_time", "%.3f" % code_perf_map["spec_syn_time"]])
                pt.add_row(["syn_time", "%.3f" % code_perf_map["syn_time"]])
                pt.add_row(["rps", "%.3f" % code_perf_map["rps"]])

                print(pt.get_string())
            else:
                if "exception" not in code_perf_map["status"]:
                    print(code_perf_map["tr"])
                    print(code_perf_map["vn_map"])
                else:
                    pass

            print("\n")
        except Exception as e:
            print("print_perf failed!", bug_file_name)
            print(str(e))
            print("\n")

    def copy_fail_codes(self, fail_list):
        if len(fail_list) > 0:
            print("\nfail_list")
            for bug_file_name in fail_list:
                print(bug_file_name)
            fail_dir_path = self.__ques_dir_path + "/code/fail"
            if not os.path.isdir(fail_dir_path):
                os.makedirs(fail_dir_path)
            for bug_file_name in fail_list:
                src_fail_file_path = self.__ques_dir_path + "/code/wrong/" + bug_file_name
                tgt_fail_file_path = fail_dir_path + "/" + bug_file_name
                copyfile(src_fail_file_path, tgt_fail_file_path)

    def run(self, timeout=60):
        print("\n\nRepair submissions in " + self.__ques_dir_path.split("/")[-1] + "\n\n")

        buggy_dir_path = self.__code_dir_path + "/wrong"
        buggy_code_map = self.__get_dir_codes(buggy_dir_path)

        perf_map = {}

        if self.__is_offline_ref:

            for pickle_file in os.listdir(self.__pickle_dir_path):
                status_list = []
                time_list = []
                rps_list = []

                pickle_path = self.__pickle_dir_path + "/" + pickle_file
                pf_str = pickle_file[:pickle_file.find(".")]
                sr = int(pf_str.split("_")[2])

                exp_idx = int(pf_str.split("_")[3])

                perf_map[sr] = {}
                perf_map[sr][exp_idx] = {}

                cluster_list_map = {}
                with open(pickle_path, 'rb') as f:
                    cluster_list_map, corr_temp_list, corr_const_list, ori_corr_code_list = pickle.load(f)

                fail_list = []

                code_perf_map = {}
                for bug_file_name, bug_code in buggy_code_map.items():
                    print(bug_file_name)


                    if any(cfs_map_equal(get_cfs_map(bug_code),
                                         get_cfs_map(ori_corr_code))
                           for ori_corr_code in ori_corr_code_list):
                        code_perf_map["match_ori"] = 1
                    else:
                        code_perf_map["match_ori"] = 0

                    start_time = time.process_time()

                    rep_perf_map = {}

                    corr_code = ""
                    try:
                        if not syntax_check(bug_code):
                            print("fail_syntax_error")
                            code_perf_map["status"] = "fail_syntax_error"
                            perf_map[sr][exp_idx][bug_file_name] = code_perf_map
                            continue

                        bug_temp_list, bug_const_list = get_temp_cons_lists([bug_code])

                        stru_match_start_time = time.process_time()
                        corr_code, rules_map, root_file_map = self.sel_corr_code(bug_code, cluster_list_map)
                        code_perf_map["stru_match_time"] = time.process_time() - stru_match_start_time

                        code_perf_map["rule_name"] = str(rules_map)
                        code_perf_map["corr_file_name"] = str(root_file_map)

                        self.rep_bug_code(bug_code,
                                        corr_code,
                                        corr_temp_list + bug_temp_list,
                                        corr_const_list + bug_const_list,
                                        rep_perf_map,
                                        timeout)
                    except Exception as e:
                        rep_perf_map["status"] = "fail_exception"

                    code_perf_map.update(rep_perf_map)
                    code_perf_map["total_time"] = time.process_time() - start_time

                    status_list.append(code_perf_map["status"])
                    if "success" in code_perf_map["status"]:
                        time_list.append(code_perf_map["total_time"])

                        code_perf_map["patch_size"] = zss_multi_func_code_distance(code_perf_map["ori_bug_code"],
                                                                                   code_perf_map["rep_code"])
                        # special case in patch size calculation
                        if code_perf_map["patch_size"] == 0 and code_perf_map["ori_bug_code"] != code_perf_map["rep_code"]:
                            code_perf_map["patch_size"] = 1
                        if code_perf_map["bug_ast_size"] == 0:
                            code_perf_map["bug_ast_size"] = 1
                        code_perf_map["rps"] = code_perf_map["patch_size"] / code_perf_map["bug_ast_size"]
                        rps_list.append(code_perf_map["rps"])
                    else:# fail
                        fail_list.append(bug_file_name)

                    self.print_perf(bug_file_name, code_perf_map)
                    perf_map[sr][exp_idx][bug_file_name] = code_perf_map

                self.print_ques_perf(sr, exp_idx, status_list, time_list, rps_list)
                self.copy_fail_codes(fail_list)
        else:# online or block repair only
            corr_code_map = self.__get_dir_codes(self.__ques_dir_path + "/code/correct")

            corr_fn_code_list = list(corr_code_map.items())

            ref_fn_code_list = list(self.__get_dir_codes(self.__ques_dir_path + "/code/reference").items())
            
            for sr in self.__sr_list:
                sel_corr_fn_code_list = []
                sel_corr_fn_code_list.extend(ref_fn_code_list)

                if sr == 0:
                    pass
                elif sr == 100:
                    sel_corr_fn_code_list.extend(corr_fn_code_list)
                else:
                    sel_corr_fn_code_list.extend(random.sample(corr_fn_code_list,
                                                            int(sr / 100 * len(corr_fn_code_list))))


                corr_temp_list, corr_const_list = get_temp_cons_lists([code for _, code in sel_corr_fn_code_list])
                perf_map[sr] = {}
                for exp_idx in range(self.__exp_time):
                    perf_map[sr][exp_idx] = {}
                    status_list = []
                    time_list = []
                    rps_list = []

                    fail_list = []
                    for bug_file_name, bug_code in buggy_code_map.items():
                        print(bug_file_name)
                        corr_code = ""

                        code_perf_map = {}

                        sel_corr_code_list = [code for _,code in sel_corr_fn_code_list]
                        if any(cfs_map_equal(get_cfs_map(bug_code),
                                             get_cfs_map(ori_corr_code))
                               for ori_corr_code in sel_corr_code_list):
                            code_perf_map["match_ori"] = 1
                        else:
                            code_perf_map["match_ori"] = 0

                        start_time = time.process_time()

                        rep_perf_map = {}
                        try:
                            if not syntax_check(bug_code):
                                print("fail_syntax_error")
                                code_perf_map["status"] = "fail_syntax_error"
                                perf_map[sr][exp_idx][bug_file_name] = code_perf_map
                                continue

                            bug_temp_list, bug_const_list = get_temp_cons_lists([bug_code])

                            # online refactoring
                            sel_fn_code_map = dict(sel_corr_fn_code_list)
                            ol_refactoring_start_time = time.process_time()

                            corr_rc_map = None
                            if self.__is_online_ref:
                                corr_rc_map = self.astar_ol_rfty(bug_code, sel_fn_code_map)
                                code_perf_map["ol_refactoring_time"] = time.process_time() - ol_refactoring_start_time
                            else:
                                corr_rc_map = self.astar_ol_rfty(bug_code, sel_fn_code_map, max_step=0)
                                code_perf_map["ol_refactoring_time"] = 0

                            gcr_start_time = time.process_time()
                            best_rc = self.astar_get_cls_rc(bug_code, corr_rc_map)
                            code_perf_map["gcr_time"] = time.process_time() - gcr_start_time

                            corr_code = best_rc.corr_code

                            code_perf_map["corr_file_name"] = best_rc.fname
                            code_perf_map["rule_name"] = best_rc.rname

                            self.rep_bug_code(bug_code,
                                                corr_code,
                                                corr_temp_list + bug_temp_list,
                                                corr_const_list + bug_const_list,
                                                rep_perf_map,
                                                timeout)
                        except Exception as e:
                            rep_perf_map["status"] = "fail_exception"

                        code_perf_map.update(rep_perf_map)
                        code_perf_map["total_time"] = time.process_time() - start_time

                        if code_perf_map["total_time"] > timeout:
                            code_perf_map["status"] = "fail_timeout"

                        status_list.append(code_perf_map["status"])

                        if "success" in code_perf_map["status"]:
                            time_list.append(code_perf_map["total_time"])
                            code_perf_map["patch_size"] = zss_multi_func_code_distance(code_perf_map["ori_bug_code"],
                                                                                       code_perf_map["rep_code"])
                            # special case in patch size calculation
                            if code_perf_map["patch_size"] == 0 and code_perf_map["ori_bug_code"] != code_perf_map["rep_code"]:
                                code_perf_map["patch_size"] = 1
                            if code_perf_map["bug_ast_size"] == 0:
                                code_perf_map["bug_ast_size"] = 1

                            code_perf_map["rps"] = code_perf_map["patch_size"] / code_perf_map["bug_ast_size"]
                            rps_list.append(code_perf_map["rps"])
                        else:
                            fail_list.append(bug_file_name)

                        self.print_perf(bug_file_name, code_perf_map)
                        perf_map[sr][exp_idx][bug_file_name] = code_perf_map

                    self.print_ques_perf(sr, exp_idx, status_list, time_list, rps_list)
                    self.copy_fail_codes(fail_list)


        return perf_map

    def sel_corr_code(self, bug_code, cluster_list_map):
        bug_cfs_map = get_cfs_map(bug_code)

        final_code_map = {}

        rules_map = {}
        root_file_map = {}

        for func_name in bug_cfs_map.keys():
            if func_name not in cluster_list_map.keys():
                continue

            bb_list, stru_list, indent_list = bug_cfs_map[func_name]

            cluster_list = cluster_list_map[func_name]
            func_code_list = []
            rules_list = []
            root_file_list = []
            for cluster in cluster_list:
                if len(cluster["stru"]) != len(stru_list):
                    continue

                if cluster["stru"] == stru_list and \
                    cluster["indent"] == indent_list:

                    func_code_list = cluster["code"]
                    rules_list = cluster["rule_id"]
                    root_file_list = cluster["root_file_name"]
                    break

            if len(func_code_list) == 0:
                bug_stru_str = cpr_stru_list(stru_list)

                min_stru_d = sys.maxsize
                for cluster in cluster_list:
                    cluster_stru_str = cpr_stru_list(cluster["stru"])
                    if abs(len(cluster_stru_str) - len(bug_stru_str)) > min_stru_d:
                        continue
                    stru_d = Levenshtein.distance(bug_stru_str, cluster_stru_str)
                    if stru_d < min_stru_d:
                        min_stru_d = stru_d

                        func_code_list = cluster["code"]
                        rules_list = cluster["rule_id"]
                        root_file_list = cluster["root_file_name"]

            min_d = sys.maxsize
            sel_func_code = ""
            sel_rules = ""
            sel_root_file = ""

            token_list_b = get_token_list("".join(bb_list))
            for i in range(len(func_code_list)):
                func_code = func_code_list[i]
                rules = rules_list[i]
                root_file = root_file_list[i]

                token_list_f = get_token_list(func_code)
                if abs(len(token_list_b)-len(token_list_f)) > min_d:
                    continue

                lev_d = smt_lev_tl_dist(token_list_b, token_list_f, min_d)
                if lev_d < min_d:
                    min_d = lev_d
                    sel_func_code = func_code
                    sel_rules = rules
                    sel_root_file = root_file

            final_code_map[func_name] = sel_func_code
            rules_map[func_name] = sel_rules
            root_file_map[func_name] = sel_root_file

        final_corr_code = "\n\n".join(list(final_code_map.values()))
        return final_corr_code, rules_map, root_file_map