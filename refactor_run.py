# Developers:   Yang Hu, et al.
# Email:    huyang0905@gmail.com

import os
import shutil
import pickle
import random
import operator
from basic_framework.refactoring import Refactoring, Reporter
from basic_framework.utils import regularize
from basic_framework.core_testing import Tester
from basic_framework.template import *


def shf_corr_path_list(ques_dir_path):
    corr_dir_path = ques_dir_path + "/code/correct"

    corr_path_list = []
    for file_name in os.listdir(corr_dir_path):
        corr_code_path = corr_dir_path + "/" + file_name
        corr_path_list.append(corr_code_path)
    random.shuffle(corr_path_list)
    return corr_path_list


def ofl_refactor_ques(ques_dir_path, timeout, max_depth, sampling_rate, exp_idx, is_resume=False, verbose=False):

    print("Current Setting:", ques_dir_path, sampling_rate, exp_idx)

    refactor_dir = ques_dir_path + "/code/refactor"
    if not os.path.isdir(refactor_dir):
        os.mkdir(refactor_dir)

    pickle_path = refactor_dir + "/refactor_sample_" + str(sampling_rate) + \
                  "_" + str(exp_idx) + ".pickle"

    if is_resume:
        if os.path.isfile(pickle_path):
            return

    corr_dir_path = ques_dir_path + "/code/correct"
    ref_dir_path = ques_dir_path + "/code/reference"
    wrong_dir_path = ques_dir_path + "/code/wrong"

    buggy_code_list = []
    for buggy_file in os.listdir(wrong_dir_path):
        buggy_file_path = wrong_dir_path + "/" + buggy_file
        with open(buggy_file_path, "r") as f:
            buggy_code = f.read()
            buggy_code = regularize(buggy_code) # change code style (tab to space)
            buggy_code_list.append(buggy_code)

    corr_path_list = []
    if sampling_rate == 100:
        corr_path_list = shf_corr_path_list(ques_dir_path)
    elif sampling_rate == 0:
        corr_path_list = []
    else:
        # sample correct programs
        import random
        corr_path_list = shf_corr_path_list(ques_dir_path)
        l = len(corr_path_list)
        corr_path_list = corr_path_list[:int(sampling_rate / 100 * l)]

    corr_code_map = {}
    for file_name in os.listdir(ref_dir_path):
        ref_code_path = ref_dir_path + "/" + file_name
        with open(ref_code_path, "r") as f:
            ref_code = regularize(f.read())
            corr_code_map[file_name] = ref_code

    # test correct programs
    t = Tester(ques_dir_path)

    pseudo_corr_dir_path = ques_dir_path + "/code/pseudo_correct"
    if not os.path.isdir(pseudo_corr_dir_path):
        os.makedirs(pseudo_corr_dir_path)

    for corr_code_path in corr_path_list:
        with open(corr_code_path, "r") as f:
            file_name = corr_code_path.split("/")[-1]
            corr_code = regularize(f.read())
            tr = t.tv_code(corr_code)
            if t.is_pass(tr):
                corr_code_map[file_name] = corr_code
            else:
                print("The so-called correct code is not correct.")
                print(tr)
                print(corr_code_path)
                shutil.move(corr_code_path, pseudo_corr_dir_path)

    print(
    	"Filter Pseudo Corr. Code:",
    	len(corr_path_list) + len(os.listdir(ref_dir_path)),
    	"->",
    	len(list(corr_code_map.values())))

    assert(len(list(corr_code_map.values())) > 0)

    # offline refactoring
    rpt = Reporter(buggy_code_list) # printing logs
    rft = Refactoring(corr_code_map, timeout, max_depth, rpt)
    cluster_list_map = rft.ofl_bfs(csv_report=verbose) # offline breadth-first-search

    if verbose:
        # to csv
        csv_path = ques_dir_path + "/ofl_rfty_" + \
               str(sampling_rate) + "_" + \
               str(exp_idx) + ".csv"
        rft.to_csv(csv_path)

    # extract expression templates, for constant repl in block repair
    corr_code_list = list(corr_code_map.values())
    temp_list, const_list = get_temp_cons_lists(corr_code_list)

    # store refacotered correct programs to pickle file
    with open(pickle_path, 'wb') as f:
        #(cluster_list_map, expression_templates, constant_list)
        pickle.dump((cluster_list_map, temp_list, const_list, corr_code_list), f, protocol=pickle.HIGHEST_PROTOCOL)


def ofl_refactor(data_dir_path, ques_name_list, sampling_rate, exp_idx):
    if ques_name_list is None:
        ques_name_list = list(os.listdir(data_dir_path))

    for ques_dir_name in ques_name_list:
        ques_dir_path = data_dir_path + "/" + ques_dir_name
        ofl_refactor_ques(ques_dir_path, timeout=None, max_depth=2, exp_idx=exp_idx, sampling_rate=sampling_rate)
