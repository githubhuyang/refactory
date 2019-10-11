# Developers:   Yang Hu, et al.
# Email:    huyang0905@gmail.com

import csv
import time
from basic_framework.statement import get_token_list
from basic_framework.cfs import get_cfs_map, get_func_cfs, get_func_map


class Reporter:
    def __init__(self, buggy_code_list, init_rep_cnt=10):
        assert (len(buggy_code_list) > 0)

        self.rep_cnt = init_rep_cnt
        self.buggy_code_cfs_map_list = []
        for buggy_code in buggy_code_list:
            buggy_cfs_map = get_cfs_map(buggy_code)
            self.buggy_code_cfs_map_list.append(buggy_cfs_map)

    def get_matching_rate(self, cluster_list_map):
        succ_cnt = 0
        for buggy_cfs_map in self.buggy_code_cfs_map_list:
            is_success = True

            for func_name in cluster_list_map.keys():
                buggy_stru_list, buggy_indent_list = [], []
                if func_name in buggy_cfs_map.keys():
                    _, buggy_stru_list, buggy_indent_list = buggy_cfs_map[func_name]

                cluster_list = cluster_list_map[func_name]

                is_partial_success = False
                for cluster in cluster_list:
                    if cluster["stru"] == buggy_stru_list and \
                            cluster["indent"] == buggy_indent_list:
                        is_partial_success = True
                        break

                if not is_partial_success:
                    is_success = False
                    break

            if is_success:
                succ_cnt += 1
        return succ_cnt/len(self.buggy_code_cfs_map_list)

    def report(self, time_left, cluster_list_map):

        if self.rep_cnt > 0:
            self.rep_cnt = self.rep_cnt - 1
            return
        self.rep_cnt = 10

        mr = self.get_matching_rate(cluster_list_map)

        stru_cnt = 1
        for func_name in cluster_list_map.keys():
            stru_cnt *= len(cluster_list_map[func_name])

        if time_left is not None:
            print("Left Time: %.2f," % time_left, "Mathing Rate: %.4f," % mr, "# Structures: " + str(stru_cnt), end='\r')
        else:
            print("Mathing Rate: %.4f," % mr, "# Structures: " + str(stru_cnt), end='\r')


class Refactoring:
    def __init__(self, corr_code_map=None, timeout=None, max_depth=10, reporter=None, debug=False, track=True):#5*60
        self.corr_code_map = corr_code_map
        self.timeout = timeout
        self.max_depth = max_depth
        self.reporter = reporter
        self.debug = debug
        self.track = track

        # function name list 
        self.__init_cfl_map()
        
        # funcName(A):[{"structure":["sig", "if"], "indent":[1,2], "code":["def A(a) ...", "def A(b) ..."]}]
        # mapping of code structure (per funcName) to multiple codes (having same structure).
        # Given buggy, match its funcName, struct, indent (with this dict), and then pick a random code
        self.cluster_list_map = {}
        self.csv_record_list = []
        self.rule_list_map = {}

    def to_csv(self, csv_path):
        with open(csv_path, 'w') as f:
            csv_w = csv.writer(f)
            csv_w.writerow(["Correct File",
                            "Function Name",
                            "Rule ID",
                            "Depth",
                            "Before-Refactor Code",
                            "After-Refactor Code"])
            for csv_record in self.csv_record_list:
                csv_w.writerow(csv_record)

    def __update(self, func_name, new_code, root_file_name, rule_id_list):
        rule_id_str = ""
        if len(rule_id_list) > 0:
            rule_id_str = ",".join(str(rule_id) for rule_id in rule_id_list)

        cluster_list = self.cluster_list_map[func_name]
        _, stru_list, indent_list = get_func_cfs(new_code)
        for cluster in cluster_list:
            if cluster["stru"] == stru_list and \
                    cluster["indent"] == indent_list:

                if root_file_name not in cluster["root_file_name"]:
                    cluster["code"].append(new_code)

                    cluster["root_file_name"].append(root_file_name)

                    cluster["rule_id"].append(rule_id_str)
                    self.rule_list_map[new_code] = rule_id_list

                    return True
                else:
                    return False



        cluster_list.append({"stru": stru_list,
                             "indent": indent_list,
                             "code":[new_code],
                             "root_file_name":[root_file_name],
                             "rule_id": [rule_id_str]})
        self.rule_list_map[new_code] = rule_id_list

        return True

    def __init_cfl_map(self):
        corr_func_list_map = {}
        for file_name, corr_code in self.corr_code_map.items():
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

        self.cfl_map = corr_func_list_map


    class TimeoutException(Exception):
        pass

    def time_checker(self, start_time):
        time_elapse = time.process_time() - start_time
        if time_elapse > self.timeout:
            raise Refactoring.TimeoutException()

    def ofl_bfs(self, csv_report=False):
        start_time = time.process_time()

        code_list_map = {}
        root_fn_lst_map = {}

        try:
            for func_name in self.cfl_map.keys():
                self.cluster_list_map[func_name] = []
                code_list_map[func_name] = []
                root_fn_lst_map[func_name] = []

            for depth in range(self.max_depth + 1):
                if self.timeout is not None:
                    self.time_checker(start_time)

                if depth == 0:
                    for func_name, corr_code_list in self.cfl_map.items():
                        for file_name, corr_code in corr_code_list:

                            init_rule_list = []
                            if self.__update(func_name, corr_code, file_name, init_rule_list):
                                code_list_map[func_name].append(corr_code)
                                root_fn_lst_map[func_name].append(file_name)

                                csv_record = [file_name, func_name, -1, depth, corr_code, corr_code]
                                self.csv_record_list.append(csv_record)

                    if self.reporter is not None:
                        if self.timeout is not None:
                            time_elapse = time.process_time() - start_time
                            self.reporter.report(self.timeout - time_elapse, self.cluster_list_map)
                            start_time = time.process_time()
                            self.timeout = self.timeout - time_elapse
                        else:
                            self.reporter.report(None, self.cluster_list_map)

                else:

                    for func_name in self.cfl_map.keys():
                        if self.timeout is not None:
                            self.time_checker(start_time)

                        tmp_code_list = []
                        tmp_root_fn_list = []

                        tmp_code_map = dict(zip(code_list_map[func_name], root_fn_lst_map[func_name]))
                        for code, root_fn in tmp_code_map.items():
                            old_rule_id_list = self.rule_list_map[code]

                            if self.timeout is not None:
                                self.time_checker(start_time)

                            if self.reporter is not None:
                                if self.timeout is not None:
                                    time_elapse = time.process_time() - start_time
                                    self.reporter.report(self.timeout - time_elapse, self.cluster_list_map)
                                    start_time = time.process_time()
                                    self.timeout = self.timeout - time_elapse
                                else:
                                    self.reporter.report(None, self.cluster_list_map)

                            for rule_id in range(1, 22):


                                rft_code_list = self.refactor(code, rule_id)

                                for rft_code in rft_code_list:
                                    if self.debug:
                                        try:
                                            compile(rft_code, '<string>', 'exec')
                                        except SyntaxError as se:
                                            print(str(se))
                                            print("Rule", rule_id)
                                            print(rft_code)
                                            print("\n\n")
                                            print(code)
                                            exit(0)
                                    new_rule_id_list = old_rule_id_list + [rule_id]
                                    if self.__update(func_name, rft_code, root_fn, new_rule_id_list):
                                        tmp_code_list.append(rft_code)
                                        tmp_root_fn_list.append(root_fn)

                                        if csv_report:
                                            csv_record = [root_fn, func_name, rule_id, depth, code, rft_code]
                                            self.csv_record_list.append(csv_record)

                        code_list_map[func_name] = tmp_code_list
                        root_fn_lst_map[func_name] = tmp_root_fn_list
        except Exception as e:
            import traceback, sys
            print(str(e), file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

        if not self.track:
            for func_name, cluster_list in self.cluster_list_map.items():
                for cluster in cluster_list:
                    del cluster["root_file_name"]
                    del cluster["rule_id"]

        return self.cluster_list_map

    def refactor(self, code, rule_id):
        if rule_id == 2:
            return self.refactor_rule_two(code)
        if rule_id == 3:
            return self.refactor_rule_three(code)
        if rule_id == 4:
            return self.refactor_rule_four(code)
        if rule_id == 5:
            return self.refactor_rule_five(code)
        if rule_id == 6:
            return self.refactor_rule_six(code)
        if rule_id == 7:
            return self.refactor_rule_seven(code)
        if rule_id == 8:
            return self.refactor_rule_eight(code)
        if rule_id == 9:
            return self.refactor_rule_nine(code)
        if rule_id == 11:
            return self.refactor_rule_eleven(code)
        if rule_id == 12:
            return self.refactor_rule_twelve(code)
        if rule_id == 13:
            return self.refactor_rule_thirteen(code)
        if rule_id == 17:
            return self.refactor_rule_seventeen(code)
        if rule_id == 21:
            return self.refactor_rule_twentyone(code)
        return []

    def refactor_rule_two(self, code):
        '''(P If(C1){B1 R1} If(C2){B2} S) <--> (P If(C1){B1 R1} Elif(C2){B2} S)'''
        refactored_code_list = [] # Each rule generates (single application) on multi-location

        cfs_map = get_cfs_map(code)
        for cfs_name in cfs_map.keys():
            not_mutated_code = ""
            for cfs_name_b in cfs_map.keys():
                if cfs_name_b != cfs_name:
                    not_mutated_code += "".join(cfs_map[cfs_name_b][0]) + "\n\n"
            
             # funcName(A):[{"structure":["sig", "if"], "indent":[1,2], "basic-blocks":["def A(a)", "if C1" "..."]}]
            bb_list, stru_list, indent_list = cfs_map[cfs_name]

            for i in range(len(bb_list)):
                if stru_list[i] == "sig": # signature/function def
                    continue

                # If block above is basic-block (bb), further indent (indent+4) 
                # (i-2, since i-1 is a dummy empty block), where i=second if block
                if stru_list[i] == "if" and \
                        i-2 >= 0 and \
                        stru_list[i-2] == "bb" and \
                        indent_list[i-2] == indent_list[i] + 4 and \
                        bb_list[i-2] != "":

                    last_ei_bb_for = False
                    for j in range(i - 1, -1, -1):
                        if indent_list[j] == indent_list[i]:
                            if stru_list[j] == "for":
                                last_ei_bb_for = True
                            break

                    # get tokens of last statement
                    token_list = get_token_list(bb_list[i-2].split("\n")[-2])
                    can_refactor = False
                    
                    # check if the last statement is return (loop to skip indents)
                    for token in token_list:
                        if token.string in ["return"] or \
                                (not last_ei_bb_for and token.string in ["continue", "break"]):
                            can_refactor = True
                            break

                    if can_refactor:
                        for j in range(i - 1, -1, -1):
                            if bb_list[j] != "" and \
                                    indent_list[j] == indent_list[i]:
                                if stru_list[j] in ["if", "elif"]:
                                    can_refactor = True
                                else:
                                    can_refactor = False
                                break

                    if can_refactor:
                        ori = "if"
                        target = "elif"

                        # Find if token and replace with elif
                        refactored_bb_code = ""
                        token_list = get_token_list(bb_list[i])
                        for token in token_list:
                            if token.string == ori:
                                l = token.start[1]
                                r = token.end[1]
                                refactored_bb_code = bb_list[i][:l] + target + bb_list[i][r:] # repl if->elif
                                break

                        # remain code retained
                        refactored_code = ""
                        for j in range(len(bb_list)):
                            if i == j:
                                refactored_code += refactored_bb_code
                            else:
                                refactored_code += bb_list[j]
                        refactored_code_list.append(not_mutated_code + refactored_code)

                # Vice-versa (replace elif to if)
                elif stru_list[i] == "elif" and \
                        i-1>=0 and \
                        stru_list[i-1] == "bb" and \
                        indent_list[i-1] == indent_list[i] + 4 and \
                        bb_list[i-1] != "":
                    last_ei_bb_for = False
                    for j in range(i - 1, -1, -1):
                        if indent_list[j] == indent_list[i]:
                            if stru_list[j] == "for":
                                last_ei_bb_for = True
                            break

                    token_list = get_token_list(bb_list[i - 1].split("\n")[-2])
                    can_refactor = False
                    for token in token_list:
                        if token.string in ["return"] or \
                                (not last_ei_bb_for and token.string in ["continue", "break"]):
                            can_refactor = True
                            break

                    if can_refactor:
                        ori = "elif"
                        target = "if"

                        refactored_bb_code = ""
                        token_list = get_token_list(bb_list[i])
                        for token in token_list:
                            if token.string == ori:
                                l = token.start[1]
                                r = token.end[1]
                                refactored_bb_code = bb_list[i][:l] + target + bb_list[i][r:]
                                break

                        refactored_code = ""
                        for j in range(len(bb_list)):
                            if i == j:
                                refactored_code += refactored_bb_code
                            else:
                                refactored_code += bb_list[j]
                        refactored_code_list.append(not_mutated_code + refactored_code)

        return refactored_code_list

    def refactor_rule_three(self, code):
        '''(P If(C1){B1 R1} {B2} S) <--> (P If(C1){B1 R1} ELSE{B2} S)'''
        refactored_code_list = []

        cfs_map = get_cfs_map(code)
        for cfs_name in cfs_map.keys():
            not_mutated_code = ""
            for cfs_name_b in cfs_map.keys():
                if cfs_name_b != cfs_name:
                    not_mutated_code += "".join(cfs_map[cfs_name_b][0]) + "\n\n"

            bb_list, stru_list, indent_list = cfs_map[cfs_name]

            for i in range(len(bb_list)):
                if stru_list[i] == "sig":
                    continue

                if stru_list[i - 1] == "bb" and \
                    indent_list[i - 1] > indent_list[i] and \
                    bb_list[i] != "":

                    idx_max_depth = i-1
                    while True:
                        if bb_list[idx_max_depth] == "" and \
                                indent_list[idx_max_depth-1]>indent_list[idx_max_depth]:
                            idx_max_depth = idx_max_depth-1
                        else:
                            break

                    can_refactor = False
                    if bb_list[idx_max_depth] == "":
                        can_refactor = False
                    else:
                        token_list = get_token_list(bb_list[idx_max_depth].split("\n")[-2])
                        for token in token_list:
                            if token.string in ["return"]:
                                can_refactor = True
                                break

                    if can_refactor:
                        can_refactor = False
                        for j in range(i - 1, -1, -1):
                            if indent_list[j] == indent_list[i]:
                                if stru_list[j] in ["if", "elif"]:
                                    can_refactor = True
                                elif stru_list[j] in ["else", "while", "for"]:
                                    can_refactor = False
                                    break
                            elif indent_list[j] < indent_list[i]:
                                break

                    if can_refactor:
                        for j in range(i + 1, len(indent_list)):
                            if indent_list[j] == indent_list[i]:
                                if stru_list[j] in ["else", "elif"]:
                                    can_refactor = False
                            elif indent_list[j] < indent_list[i]:
                                break

                    if can_refactor:
                        refactored_bb_code = ""
                        if stru_list[i] not in ["else", "elif"]:
                            refactored_code = ""
                            add_indentation = False
                            for j in range(len(bb_list)):
                                if i == j:
                                    indent_str = "".join([" " for k in range(indent_list[i])])
                                    refactored_code += indent_str + "else:\n"
                                    add_indentation = True
                                if add_indentation:
                                    if indent_list[j] < indent_list[i]:
                                        refactored_code += bb_list[j]
                                        add_indentation = False
                                    else:
                                        ln_list = bb_list[j].split("\n")
                                        for ln in ln_list:
                                            if ln != "":
                                                refactored_code += "    " + ln + "\n"
                                else:
                                    refactored_code += bb_list[j]

                            refactored_code_list.append(not_mutated_code + refactored_code)
                        elif stru_list[i] == "else":
                            refactored_code = ""
                            del_indentation = False
                            for j in range(len(bb_list)):
                                if i == j:
                                    del_indentation = True
                                elif del_indentation:
                                    if indent_list[j] <= indent_list[i]:
                                        refactored_code += bb_list[j]
                                        del_indentation = False
                                    else:
                                        ln_list = bb_list[j].split("\n")
                                        for ln in ln_list:
                                            if ln != "":
                                                refactored_code += ln[4:] + "\n"
                                else:
                                    refactored_code += bb_list[j]
                            refactored_code_list.append(not_mutated_code + refactored_code)

        return refactored_code_list

    def refactor_rule_four(self, code):
        '''P S -> P If(*){Pass} S
           P If(C1){B1}B2 S-> P If(C1){B1}Else{Pass}B2 S
           P Elif(C1){B1}B2 S-> P Elif(C1){B1}Else{Pass}B2 S
           P If(C1){B1}B2 S-> P If(C1){B1}Elif(*){Pass}B2 S
        '''
        refactored_code_list = []

        cfs_map = get_cfs_map(code)
        for cfs_name in cfs_map.keys():
            not_mutated_code = ""
            for cfs_name_b in cfs_map.keys():
                if cfs_name_b != cfs_name:
                    not_mutated_code += "".join(cfs_map[cfs_name_b][0]) + "\n\n"

            bb_list, stru_list, indent_list = cfs_map[cfs_name]

            for i in range(len(bb_list)):
                if stru_list[i] == "sig":
                    continue

                if stru_list[i] in ["elif", "else"]:
                    continue

                indent_str = "".join([" " for k in range(indent_list[i])])

                refactored_bb = ""
                refactored_bb += indent_str + "if True: # Any Condition\n"
                refactored_bb += indent_str + "    pass\n"

                refactored_code = ""
                for j in range(len(bb_list)):
                    if j == i:
                        refactored_code += refactored_bb
                    refactored_code += bb_list[j]

                if refactored_code not in refactored_code_list:
                    refactored_code_list.append(not_mutated_code + refactored_code)

            for i in range(len(bb_list)):
                if stru_list[i] == "sig":
                    continue
                if stru_list[i] == "if":
                    pos = -1
                    for j in range(i + 1, len(bb_list)):
                        if indent_list[j] < indent_list[i]:
                            pos = -1
                            break
                        elif indent_list[j] == indent_list[i] and \
                                stru_list[j] != "elif":
                            pos = j
                            break

                    if stru_list[pos] == "else":
                        continue

                    indent_str = "".join([" " for k in range(indent_list[i])])

                    refactored_bb = ""
                    refactored_bb += indent_str + "elif True: # Any Condition\n"
                    refactored_bb += indent_str + "    pass\n"

                    refactored_code = ""
                    for j in range(len(bb_list)):
                        if j == pos:
                            refactored_code += refactored_bb
                        refactored_code += bb_list[j]

                    if refactored_code not in refactored_code_list:
                        refactored_code_list.append(not_mutated_code + refactored_code)

            for i in range(len(bb_list)):
                if stru_list[i] == "sig":
                    continue
                if stru_list[i] == "if":
                    pos = -1
                    for j in range(i + 1, len(bb_list)):
                        if indent_list[j] < indent_list[i]:
                            pos = -1
                            break
                        elif indent_list[j] == indent_list[i] and stru_list[j] != "elif":
                            pos = j
                            break

                    if stru_list[pos] == "else":
                        continue

                    indent_str = "".join([" " for k in range(indent_list[i])])

                    refactored_bb = ""
                    refactored_bb += indent_str + "else:\n"
                    refactored_bb += indent_str + "    pass\n"

                    refactored_code = ""
                    for j in range(len(bb_list)):
                        if j == pos:
                            refactored_code += refactored_bb
                        refactored_code += bb_list[j]

                    if refactored_code not in refactored_code_list:
                        refactored_code_list.append(not_mutated_code + refactored_code)
        return refactored_code_list

    def refactor_rule_five(self, code):
        '''P B S -> P If(False){*}B S
           P If(C1){B1}B2 S-> P If(C1){B1}Elif(False){*}B2 S
        '''
        refactored_code_list = []

        cfs_map = get_cfs_map(code)
        for cfs_name in cfs_map.keys():
            not_mutated_code = ""
            for cfs_name_b in cfs_map.keys():
                if cfs_name_b != cfs_name:
                    not_mutated_code += "".join(cfs_map[cfs_name_b][0]) + "\n\n"

            bb_list, stru_list, indent_list = cfs_map[cfs_name]

            for i in range(len(bb_list)):
                if stru_list[i] == "sig":
                    continue

                if stru_list[i] in ["elif", "else"]:
                    continue

                indent_str = "".join([" " for k in range(indent_list[i])])

                refactored_bb = ""
                refactored_bb += indent_str + "if False:\n"
                refactored_bb += indent_str + "    pass # Any Block\n"

                refactored_code = ""
                for j in range(len(bb_list)):
                    if j == i:
                        refactored_code += refactored_bb
                    refactored_code += bb_list[j]

                if refactored_code not in refactored_code_list:
                    refactored_code_list.append(not_mutated_code + refactored_code)

            for i in range(len(bb_list)):
                if stru_list[i] == "sig":
                    continue
                if stru_list[i] == "if":
                    pos = -1
                    for j in range(i + 1, len(bb_list)):
                        if indent_list[j] < indent_list[i]:
                            pos = -1
                            break
                        elif indent_list[j] == indent_list[i] and stru_list[j] != "elif":
                            pos = j
                            break

                    if stru_list[pos] == "else":
                        continue

                    indent_str = "".join([" " for k in range(indent_list[i])])

                    refactored_bb = ""
                    refactored_bb += indent_str + "elif False:\n"
                    refactored_bb += indent_str + "    pass # Any Block\n"

                    refactored_code = ""
                    for j in range(len(bb_list)):
                        if j == pos:
                            refactored_code += refactored_bb
                        refactored_code += bb_list[j]

                    if refactored_code not in refactored_code_list:
                        refactored_code_list.append(not_mutated_code + refactored_code)

        return refactored_code_list

    def refactor_rule_six(self, code):
        '''P If(C1 and C2){B1}B2 S -> P If(C1){If(C2){B1}}B2 S
           P If(C1 and C2){B1}B2 S -> P If(True){If(C1 and C2){B1}}B2 S
           P If(C1 and C2){B1}B2 S -> P If(C1 and C2){If(True){B1}}B2 S
        '''
        refactored_code_list = []

        cfs_map = get_cfs_map(code)
        for cfs_name in cfs_map.keys():
            not_mutated_code = ""
            for cfs_name_b in cfs_map.keys():
                if cfs_name_b != cfs_name:
                    not_mutated_code += "".join(cfs_map[cfs_name_b][0]) + "\n\n"

            bb_list, stru_list, indent_list = cfs_map[cfs_name]

            for i in range(len(bb_list)):
                if stru_list[i] == "if":
                    can_split = True
                    for j in range(i+1, len(bb_list)):
                        if indent_list[j] == indent_list[i]:
                            if stru_list[j] in ["elif", "else"]:
                                can_split = False
                            break

                    if can_split:
                        l = -1
                        for token_b in get_token_list(bb_list[i]):
                            if token_b.string == "if":
                                l = token_b.start[1] + 3
                                break
                        r = -1
                        for token_b in get_token_list(bb_list[i]):
                            if token_b.string == ":":
                                r = token_b.start[1]
                        cond = bb_list[i][l:r].strip()
                        if "and" in cond and "(" not in cond and ")" not in cond and "or" not in cond:
                            m = cond.find("and")
                            cond1 = cond[:m].strip()
                            cond2 = cond[m + 4:].strip()

                            indent_str = "".join([" " for k in range(indent_list[i])])

                            refactored_bb = ""
                            refactored_bb += indent_str + "if " + cond1 + ":\n"
                            refactored_bb += indent_str + "    if " + cond2 + ":\n"

                            refactored_code = ""
                            add_indent = False
                            for j in range(len(bb_list)):
                                if i == j:
                                    refactored_code += refactored_bb
                                    add_indent = True
                                elif add_indent:
                                    if indent_list[j] <= indent_list[i]:
                                        refactored_code += bb_list[j]
                                        add_indent = False
                                    else:
                                        for ln in bb_list[j].split("\n"):
                                            if ln != "":
                                                refactored_code += "    " + ln + "\n"
                                else:
                                    refactored_code += bb_list[j]
                            refactored_code_list.append(not_mutated_code + refactored_code)

                        indent_str = "".join([" " for k in range(indent_list[i])])

                        refactored_bb = ""
                        refactored_bb += indent_str + "if True" + ":\n"
                        refactored_bb += indent_str + "    if " + cond + ":\n"

                        refactored_code = ""
                        add_indent = False
                        for j in range(len(bb_list)):
                            if i == j:
                                refactored_code += refactored_bb
                                add_indent = True
                            elif add_indent:
                                if indent_list[j] <= indent_list[i]:
                                    refactored_code += bb_list[j]
                                    add_indent = False
                                else:
                                    for ln in bb_list[j].split("\n"):
                                        if ln != "":
                                            refactored_code += "    " + ln + "\n"
                            else:
                                refactored_code += bb_list[j]
                        refactored_code_list.append(not_mutated_code + refactored_code)

                        indent_str = "".join([" " for k in range(indent_list[i])])

                        refactored_bb = ""
                        refactored_bb += indent_str + "if " + cond + ":\n"
                        refactored_bb += indent_str + "    if True" + ":\n"

                        refactored_code = ""
                        add_indent = False
                        for j in range(len(bb_list)):
                            if i == j:
                                refactored_code += refactored_bb
                                add_indent = True
                            elif add_indent:
                                if indent_list[j] <= indent_list[i]:
                                    refactored_code += bb_list[j]
                                    add_indent = False
                                else:
                                    for ln in bb_list[j].split("\n"):
                                        if ln != "":
                                            refactored_code += "    " + ln + "\n"
                            else:
                                refactored_code += bb_list[j]
                        refactored_code_list.append(not_mutated_code + refactored_code)

        return refactored_code_list

    def refactor_rule_seven(self, code):
        '''P If(C1){If(C2){B1}}B2 S -> P If(C1 and C2){B1}B2 S'''
        refactored_code_list = []

        cfs_map = get_cfs_map(code)
        for cfs_name in cfs_map.keys():
            not_mutated_code = ""
            for cfs_name_b in cfs_map.keys():
                if cfs_name_b != cfs_name:
                    not_mutated_code += "".join(cfs_map[cfs_name_b][0]) + "\n\n"

            bb_list, stru_list, indent_list = cfs_map[cfs_name]

            for i in range(len(bb_list)):
                if stru_list[i] == "if" and \
                    i + 2 < len(bb_list) and \
                    bb_list[i+1] == "" and \
                    stru_list[i+2] == "if" and \
                    indent_list[i]+4 == indent_list[i+2]:
                    can_combine = True
                    for j in range(i+1, len(bb_list)):
                        if indent_list[j] == indent_list[i]:
                            if stru_list[j] in ["elif", "else"]:
                                can_combine = False
                            break
                    if can_combine:
                        for j in range(i + 3, len(bb_list)):
                            if indent_list[j] == indent_list[i + 2]:
                                if stru_list[j] in ["elif", "else"]:
                                    can_combine = False
                                    break
                                elif bb_list[j] != "":
                                    can_combine = False
                                    break
                            if indent_list[j] < indent_list[i + 2]:
                                break
                    if can_combine:
                        l = -1
                        for token_b in get_token_list(bb_list[i]):
                            if token_b.string == "if":
                                l = token_b.end[1]
                                break

                        r = -1
                        for token_b in get_token_list(bb_list[i]):
                            if token_b.string == ":":
                                r = token_b.start[1]

                        cond1 = bb_list[i][l:r].strip()

                        l = -1
                        for token_b in get_token_list(bb_list[i+2]):
                            if token_b.string == "if":
                                l = token_b.end[1]
                                break

                        r = -1
                        for token_b in get_token_list(bb_list[i+2]):
                            if token_b.string == ":":
                                r = token_b.start[1]

                        cond2 = bb_list[i+2][l:r].strip()

                        indent_str = "".join([" " for k in range(indent_list[i])])
                        refactored_bb = ""
                        refactored_bb += indent_str + "if " + cond1 + " and " + cond2 + ":\n"

                        del_indent = False
                        refactored_code = ""
                        for j in range(len(bb_list)):
                            if j == i:
                                refactored_code += refactored_bb
                                del_indent = True
                                continue
                            elif j == i + 1 or j == i + 2:
                                continue
                            if del_indent:
                                if indent_list[j] <= indent_list[i]:
                                    refactored_code += bb_list[j]
                                    del_indent = False
                                else:
                                    ln_list = bb_list[j].split("\n")
                                    for ln in ln_list:
                                        if ln != "":
                                            refactored_code += ln[4:] + "\n"
                            else:
                                refactored_code += bb_list[j]

                        refactored_code_list.append(not_mutated_code + refactored_code)

        return refactored_code_list

    def refactor_rule_eight(self, code):
        '''P Elif(C1){...} S -> P Else{If(C1){...}} S'''
        refactored_code_list = []

        cfs_map = get_cfs_map(code)
        for cfs_name in cfs_map.keys():
            not_mutated_code = ""
            for cfs_name_b in cfs_map.keys():
                if cfs_name_b != cfs_name:
                    not_mutated_code += "".join(cfs_map[cfs_name_b][0]) + "\n\n"

            bb_list, stru_list, indent_list = cfs_map[cfs_name]

            for i in range(len(bb_list)):
                if stru_list[i] == 'elif':
                    l = -1
                    for token_b in get_token_list(bb_list[i]):
                        if token_b.string == "elif":
                            l = token_b.end[1]
                            break
                    r = -1
                    for token_b in get_token_list(bb_list[i]):
                        if token_b.string == ":":
                            r = token_b.start[1]

                    cond = bb_list[i][l:r].strip()
                    indent_str = "".join([" " for k in range(indent_list[i])])

                    refactored_bb = ""
                    refactored_bb += indent_str + "else:\n"
                    refactored_bb += indent_str + "    if " + cond + ":\n"

                    add_indent = False
                    refactored_code = ""
                    for j in range(len(bb_list)):
                        if i == j:
                            refactored_code += refactored_bb
                            add_indent = True
                            continue
                        if add_indent:
                            if indent_list[j] < indent_list[i] or \
                                    (indent_list[j] == indent_list[i] and \
                                    stru_list[j] not in ["else", "elif"]):
                                refactored_code += bb_list[j]
                                add_indent = False
                            else:
                                ln_list = bb_list[j].split("\n")
                                for ln in ln_list:
                                    if ln != "":
                                        refactored_code += "    "+ ln + "\n"
                        else:
                            refactored_code += bb_list[j]
                    refactored_code_list.append(not_mutated_code + refactored_code)
        return refactored_code_list

    def refactor_rule_nine(self, code):
        '''P Else{If(C1){...}} S -> P Elif(C1){...} S'''
        refactored_code_list = []

        cfs_map = get_cfs_map(code)
        for cfs_name in cfs_map.keys():
            not_mutated_code = ""
            for cfs_name_b in cfs_map.keys():
                if cfs_name_b != cfs_name:
                    not_mutated_code += "".join(cfs_map[cfs_name_b][0]) + "\n\n"

            bb_list, stru_list, indent_list = cfs_map[cfs_name]

            for i in range(len(bb_list)):
                if stru_list[i] == 'else' and \
                        i + 2 < len(bb_list) and \
                        bb_list[i+1] == "" and \
                        stru_list[i+2] == "if":

                    can_combine = True
                    for j in range(i+3, len(bb_list)):
                        if indent_list[j] == indent_list[i+2]:
                            if bb_list[j] != "":
                                can_combine = False
                                break
                        elif indent_list[j] < indent_list[i+2]:
                            break

                    if not can_combine:
                        continue

                    l = -1
                    for token_b in get_token_list(bb_list[i+2]):
                        if token_b.string == "if":
                            l = token_b.end[1]
                            break
                    r = -1
                    for token_b in get_token_list(bb_list[i+2]):
                        if token_b.string == ":":
                            r = token_b.start[1]

                    cond = bb_list[i+2][l:r].strip()
                    indent_str = "".join([" " for k in range(indent_list[i])])

                    refactored_bb = ""
                    refactored_bb += indent_str + "elif " + cond + ":\n"

                    refactored_code = ""
                    dec_indent = False
                    for j in range(len(bb_list)):
                        if i == j:
                            refactored_code += refactored_bb
                            dec_indent = True
                            continue
                        if j == i+1 or j == i+2:
                            continue
                        if dec_indent:
                            if indent_list[j] <= indent_list[i]:
                                refactored_code += bb_list[j]
                                dec_indent = False
                            else:
                                ln_list = bb_list[j].split("\n")
                                for ln in ln_list:
                                    if ln != "":
                                        refactored_code += ln[4:] + "\n"
                        else:
                            refactored_code += bb_list[j]
                    refactored_code_list.append(not_mutated_code + refactored_code)
        return refactored_code_list

    def refactor_rule_eleven(self, code):
        '''P For(... in lst){B1} S -> P If(len(lst)>0){For(... in lst){B1}} S
           P For(... in lst){B1} S -> P If(len(lst)<=0){Pass}Else{For(... in lst){B1}} S
           P While(C1){B1} S -> P If(C1){While(C1){B1}} S
           P While(C1){B1} S -> P If(!C1){Pass}Else{While(C1){B1}} S
        '''

        refactored_code_list = []

        cfs_map = get_cfs_map(code)
        for cfs_name in cfs_map.keys():
            not_mutated_code = ""
            for cfs_name_b in cfs_map.keys():
                if cfs_name_b != cfs_name:
                    not_mutated_code += "".join(cfs_map[cfs_name_b][0]) + "\n\n"

            bb_list, stru_list, indent_list = cfs_map[cfs_name]

            for i in range(len(bb_list)):
                if stru_list[i] == "for":
                    refactored_bb_list = []

                    token_list = get_token_list(bb_list[i])
                    for token in token_list:
                        if token.string == "enumerate":
                            l = token.end[1]
                            r = -1
                            for token_b in token_list:
                                if token_b.string == ":":
                                    r = token_b.start[1]
                                    # no break, need the last semicolon

                            seq_code = bb_list[i][l:r].strip()

                            indent_str = "".join([" " for k in range(indent_list[i])])
                            refactored_bb = ""
                            refactored_bb += indent_str + "if len(" + seq_code + ") > 0:\n"
                            refactored_bb_list.append(refactored_bb)

                            refactored_bb = ""
                            refactored_bb += indent_str + "if len(" + seq_code + ") == 0:\n"
                            refactored_bb += indent_str + "    pass\n"
                            refactored_bb += indent_str + "else:\n"
                            refactored_bb_list.append(refactored_bb)
                            break
                        else:
                            l = -1
                            for token_b in token_list:
                                if token_b.string == "in":
                                    l = token_b.end[1]
                                    break

                            r = -1
                            for token_b in token_list:
                                if token_b.string == ":":
                                    r = token_b.start[1]
                                    # no break, need the last semicolon

                            range_code = bb_list[i][l:r].strip()

                            indent_str = "".join([" " for k in range(indent_list[i])])
                            refactored_bb = ""
                            refactored_bb += indent_str + "if len(" + range_code + ") > 0:\n"
                            refactored_bb_list.append(refactored_bb)

                            refactored_bb = ""
                            refactored_bb += indent_str + "if len(" + range_code + ") == 0:\n"
                            refactored_bb += indent_str + "    pass\n"
                            refactored_bb += indent_str + "else:\n"
                            refactored_bb_list.append(refactored_bb)
                            break

                    for refactored_bb in refactored_bb_list:
                        refactored_code = ""
                        add_indent = False
                        for j in range(len(bb_list)):
                            if i == j:
                                refactored_code += refactored_bb
                                refactored_code += "    " + bb_list[j]
                                add_indent = True
                                continue
                            if add_indent:
                                if indent_list[j] <= indent_list[i]:
                                    refactored_code += bb_list[j]
                                    add_indent = False
                                else:
                                    ln_list = bb_list[j].split("\n")
                                    for ln in ln_list:
                                        if ln != "":
                                            refactored_code += "    " + ln + "\n"
                            else:
                                refactored_code += bb_list[j]
                        refactored_code_list.append(not_mutated_code + refactored_code)
                elif stru_list[i] == "while":
                    refactored_bb_list = []
                    token_list = get_token_list(bb_list[i])

                    l = -1
                    for token_b in token_list:
                        if token_b.string == "while":
                            l = token_b.end[1]
                            break

                    r = -1
                    for token_b in token_list:
                        if token_b.string == ":":
                            r = token_b.start[1]
                    cond_code = bb_list[i][l:r].strip()

                    indent_str = "".join([" " for k in range(indent_list[i])])
                    refactored_bb = ""
                    refactored_bb += indent_str + "if " + cond_code + ":\n"
                    refactored_bb_list.append(refactored_bb)

                    refactored_bb = ""
                    refactored_bb += indent_str + "if not (" + cond_code + "):\n"
                    refactored_bb += indent_str + "    pass\n"
                    refactored_bb += indent_str + "else:\n"
                    refactored_bb_list.append(refactored_bb)

                    for refactored_bb in refactored_bb_list:
                        refactored_code = ""
                        add_indent = False
                        for j in range(len(bb_list)):
                            if i == j:
                                refactored_code += refactored_bb
                                refactored_code += "    " + bb_list[j]
                                add_indent = True
                                continue
                            if add_indent:
                                if indent_list[j] <= indent_list[i]:
                                    refactored_code += bb_list[j]
                                    add_indent = False
                                else:
                                    ln_list = bb_list[j].split("\n")
                                    for ln in ln_list:
                                        if ln != "":
                                            refactored_code += "    " + ln + "\n"
                            else:
                                refactored_code += bb_list[j]
                        refactored_code_list.append(not_mutated_code + refactored_code)
        return refactored_code_list

    def refactor_rule_twelve(self, code):
        '''P While(C1){B1} S -> P While(True){If(!C1){Break}B1} S'''

        refactored_code_list = []

        cfs_map = get_cfs_map(code)
        for cfs_name in cfs_map.keys():
            not_mutated_code = ""
            for cfs_name_b in cfs_map.keys():
                if cfs_name_b != cfs_name:
                    not_mutated_code += "".join(cfs_map[cfs_name_b][0]) + "\n\n"

            bb_list, stru_list, indent_list = cfs_map[cfs_name]

            for i in range(len(bb_list)):
                if stru_list[i] == "while":
                    token_list = get_token_list(bb_list[i])
                    l = -1
                    for token_b in token_list:
                        if token_b.string == "while":
                            l = token_b.end[1]
                            break
                    r = -1
                    for token_b in token_list:
                        if token_b.string == ":":
                            r = token_b.start[1]

                    cond_code = bb_list[i][l:r].strip()

                    refactored_bb = ""
                    indent_str = "".join([" " for k in range(indent_list[i])])
                    refactored_bb += indent_str + "while True:\n"
                    refactored_bb += indent_str + "    if not (" + cond_code + "):\n"
                    refactored_bb += indent_str + "        break\n"

                    refactored_code = ""
                    for j in range(len(bb_list)):
                        if i == j:
                            refactored_code += refactored_bb
                        else:
                            refactored_code += bb_list[j]
                    refactored_code_list.append(not_mutated_code + refactored_code)
        return refactored_code_list

    def refactor_rule_thirteen(self, code):
        '''P If(C1){B1 J1} S -> P While(C1){B1 J1} S
           P If(C1){B1} S -> P While(C1){B1 break} S
           Note: no continue or break is in B1
        '''
        refactored_code_list = []

        cfs_map = get_cfs_map(code)
        for cfs_name in cfs_map.keys():
            not_mutated_code = ""
            for cfs_name_b in cfs_map.keys():
                if cfs_name_b != cfs_name:
                    not_mutated_code += "".join(cfs_map[cfs_name_b][0]) + "\n\n"

            bb_list, stru_list, indent_list = cfs_map[cfs_name]

            for i in range(len(bb_list)):
                if stru_list[i] == "if":
                    can_refactor = True
                    for j in range(i+1,len(bb_list)):
                        if indent_list[i] < indent_list[j] and stru_list[j] == "bb":
                            ln_list = bb_list[j].split("\n")
                            for ln in ln_list:
                                if ln !=  "":
                                    token_list = get_token_list(ln)
                                    if any([token.string in ["continue", "break"] for token in token_list]):
                                        can_refactor = False
                                        break
                            if not can_refactor:
                                break
                        elif indent_list[i] == indent_list[j]:
                            if stru_list[j] in ["else", "elif"]:
                                can_refactor = False
                                break
                        elif indent_list[j] < indent_list[i]:
                            break

                    if not can_refactor:
                        continue


                    l = -1
                    r = -1
                    refactored_bb = ""
                    token_list = get_token_list(bb_list[i])
                    for token in token_list:
                        if token.string == "if":
                            l = token.start[1]
                            r = token.end[1]
                            refactored_bb += bb_list[i][:l] + "while " + bb_list[i][r:].strip() + "\n"
                            break

                    refactored_code = ""
                    beg_search = False
                    for j in range(len(bb_list)):
                        if i == j:
                            refactored_code += refactored_bb
                            beg_search = True
                        elif beg_search:
                            if indent_list[j] <= indent_list[i]:
                                indent_str = "".join([" " for k in range(indent_list[i])])

                                need_break = True
                                ln_list = bb_list[j-1].split("\n")
                                for ln in ln_list:
                                    if ln != "":
                                        token_list = get_token_list(ln)
                                        if any([token.string == "return" for token in token_list]):
                                            need_break = False
                                            break

                                if need_break: # this if condition can also be removed
                                    refactored_code += indent_str + "    break\n"
                                refactored_code += bb_list[j]
                                beg_search = False
                            else:
                                refactored_code += bb_list[j]
                        else:
                            refactored_code += bb_list[j]
                    refactored_code_list.append(not_mutated_code + refactored_code)

        return refactored_code_list

    def refactor_rule_seventeen(self, code):
        '''P B1 S-> P For(new_v in range(1)){B1} S
           Note: no continue or break is in B1
        '''
        refactored_code_list = []

        cfs_map = get_cfs_map(code)
        for cfs_name in cfs_map.keys():
            not_mutated_code = ""
            for cfs_name_b in cfs_map.keys():
                if cfs_name_b != cfs_name:
                    not_mutated_code += "".join(cfs_map[cfs_name_b][0]) + "\n\n"

            bb_list, stru_list, indent_list = cfs_map[cfs_name]

            for i in range(len(bb_list)):
                if stru_list[i] == "bb" and bb_list[i] != "":
                    ln_list = bb_list[i].split("\n")

                    can_refactor = True
                    for ln in ln_list:
                        if ln != "":
                            token_list = get_token_list(ln)
                            if any([token.string in ["break", "continue"] for token in token_list]):
                                can_refactor = False
                                break

                    if not can_refactor:
                        continue

                    for j in range(len(ln_list)-1):
                        for k in range(j, len(ln_list)-1):
                            refactored_bb = ""
                            indent_str = "".join([" " for id in range(indent_list[i])])

                            for l in range(len(ln_list)-1):

                                if l == j:
                                    refactored_bb += indent_str + "for added_loop in range(1):\n"
                                    refactored_bb += "    " + ln_list[l] + "\n"
                                else:
                                    refactored_bb += ln_list[l] + "\n"

                            refactored_code = ""
                            for l in range(len(bb_list)):
                                if l == i:
                                    refactored_code += refactored_bb
                                else:
                                    refactored_code += bb_list[l]
                            refactored_code_list.append(not_mutated_code + refactored_code)
                elif stru_list[i] in ["for", "while", "if"]:
                    indent_str = "".join([" " for id in range(indent_list[i])])
                    refactored_bb = ""
                    refactored_bb += indent_str + "for added_loop in range(1):\n"

                    refactored_code = ""
                    can_refactor = True
                    add_indent = False
                    for j in range(len(bb_list)):
                        if i == j:
                            refactored_code += refactored_bb
                            add_indent = True
                        if add_indent:
                            if indent_list[j] < indent_list[i]:
                                refactored_code += bb_list[j]
                                add_indent = False
                            else:
                                ln_list = bb_list[j].split("\n")[:-1]

                                for ln in ln_list:
                                    if ln != "":
                                        token_list = get_token_list(ln)
                                        if any([token.string in ["break", "continue"] for token in token_list]):
                                            can_refactor = False
                                            break
                                if not can_refactor:
                                    break

                                for ln in ln_list:
                                    if ln != "":
                                        refactored_code += "    " + ln + "\n"
                        else:
                            refactored_code += bb_list[j]
                    if can_refactor:
                        refactored_code_list.append(not_mutated_code + refactored_code)
        return refactored_code_list

    def refactor_rule_twentyone(self, code):
        '''P Else{B1} S -> P Elif(True){B1} S'''
        refactored_code_list = []

        cfs_map = get_cfs_map(code)
        for cfs_name in cfs_map.keys():
            not_mutated_code = ""
            for cfs_name_b in cfs_map.keys():
                if cfs_name_b != cfs_name:
                    not_mutated_code += "".join(cfs_map[cfs_name_b][0]) + "\n\n"

            bb_list, stru_list, indent_list = cfs_map[cfs_name]

            for i in range(len(bb_list)):
                if stru_list[i] == "else":
                    refactored_code = "".join(bb_list[:i])
                    refactored_code += bb_list[i].replace("else", "elif True")
                    refactored_code += "".join(bb_list[i+1:])
                    refactored_code_list.append(not_mutated_code + refactored_code)

        return refactored_code_list