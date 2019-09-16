# Developers:   Yang Hu, et al.
# Email:    huyang0905@gmail.com

import os
import csv
from basic_framework.cfs import get_cfs_map, cfs_map_equal
from basic_framework.repair import BlockRepair, ORO


csv_header = ["Question", "Sampling Rate", "Experiment ID", "File Name",
            "Status", "Match (Rfty Code)", "Match (Ori Code)",
            "Buggy Code", "Buggy Mutation",
            "Refactored Correct Code", "Original Correct File Name", "Rule ID", "Repair",
            "Stru. Matching Time", "Online Refactoring Time", "GCR Time", "Stru. Mutation Time",
            "Block Mapping Time", "Variable Mapping Time",
            "Specification&Synthesis Time", "Total Time",
            "#Passed Test Case", "#Test Case",
            "RPS"]

key_list = ["status", "match", "match_ori",
            "ori_bug_code", "align_bug_code",
            "corr_code", "corr_file_name", "rule_name", "rep_code",
            "stru_match_time", "ol_refactoring_time", "gcr_time", "mut_time",
            "bb_map_time", "vn_map_time",
            "spec_syn_time", "total_time",
            "cnt_case_pass", "cnt_case_all",
            "rps"]


def gen_row(ques_name, sr, exp_idx, file_name, code_perf_map):
    global key_list

    row = [ques_name, sr, exp_idx, file_name]
    for key in key_list:
        ele = "N/A"
        if key in code_perf_map.keys():
            ele = code_perf_map[key]

        if ele != "N/A" and ("time" in key or key == "rps"):
            row.append("%.3f" % ele)
        else:
            row.append(ele)
    return row


def perf_to_csv(ques_dir_path, perf_map_dict, online_or_offline):
    global csv_header

    ques_name = ques_dir_path.split("/")[-1]
    csv_path = ques_dir_path + "/refactory_" + online_or_offline + ".csv"

    with open(csv_path, 'w') as f:
        csv_w = csv.writer(f)
        csv_w.writerow(csv_header)

        for sr in perf_map_dict.keys():
            for exp_idx in perf_map_dict[sr].keys():
                for file_name in perf_map_dict[sr][exp_idx].keys():
                    code_perf_map = perf_map_dict[sr][exp_idx][file_name]
                    if "tr" in code_perf_map.keys():
                        code_perf_map["cnt_case_pass"] = list(code_perf_map["tr"].values()).count(True)
                        code_perf_map["cnt_case_all"] = len(list(code_perf_map["tr"].values()))

                    row = gen_row(ques_name, sr, exp_idx, file_name, code_perf_map)
                    csv_w.writerow(row)


def repair_ques(ques_dir_path, is_offline_ref, is_online_ref, is_mutation, sr_list, exp_time):
    br = BlockRepair(ques_dir_path, is_offline_ref=is_offline_ref, is_online_ref=is_online_ref, is_mutation=is_mutation, sr_list=sr_list, exp_time=exp_time)
    return br.run()


def repair_dataset(data_dir_path, ques_name_list, is_offline_ref, is_online_ref, sr_list, exp_time, is_csv_log, is_mutation):
    if ques_name_list is None:
        ques_name_list = list(os.listdir(data_dir_path))

    for ques_dir_name in ques_name_list:
        ques_dir_path = data_dir_path + "/" + ques_dir_name

        ques_perf_map = repair_ques(ques_dir_path, is_offline_ref, is_online_ref, is_mutation, sr_list, exp_time)

        online_or_offline = None
        if is_online_ref:
            online_or_offline = "online"
        elif is_offline_ref:
            online_or_offline = "offline"
        else:
            online_or_offline = "norefactor"


        if is_csv_log:
            perf_to_csv(ques_dir_path, ques_perf_map, online_or_offline)


def oro_dataset(data_dir_path, ques_name_list, sr_list, exp_time):
    if ques_name_list is None:
        ques_name_list = list(os.listdir(data_dir_path))

    for ques_dir_name in ques_name_list:
        ques_dir_path = data_dir_path + "/" + ques_dir_name

        oro_ques(ques_dir_path, sr_list, exp_time)


def oro_ques(ques_dir_path, sr_list, exp_time):
    o = ORO(ques_dir_path, sr_list=sr_list, exp_time=exp_time)
    o.run()


def cmb_csv_logs(data_dir_path, online_or_offline):
    """Combine csvs into one"""
    global csv_header

    ir_dir_path = os.getcwd() + "/intermediate_results"
    if not os.path.isdir(ir_dir_path):
        os.makedirs(ir_dir_path)

    global_csv_path = ir_dir_path + "/refactory_" + online_or_offline + ".csv"
    with open(global_csv_path, 'w') as f:
        csv_w = csv.DictWriter(f, fieldnames=csv_header)
        csv_w.writeheader()
        for ques_dir_name in os.listdir(data_dir_path):
            ques_dir_path = data_dir_path + "/" + ques_dir_name

            local_csv_path = ques_dir_path + "/refactory_" + online_or_offline + ".csv"

            if os.path.isfile(local_csv_path):
                with open(local_csv_path, "r") as csvfile:
                    csv_r = csv.DictReader(csvfile)  # reader
                    for row in csv_r:
                        csv_w.writerow(row)


    import pandas as pd
    df = pd.read_csv(global_csv_path, header=0)
    print(df.groupby("Status").count()[['File Name']])
    print("\n\n")
    print(df.groupby("Match (Rfty Code)").count()[['File Name']])