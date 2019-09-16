import argparse
from refactor_run import ofl_refactor
from block_repair_run import repair_dataset, oro_dataset, cmb_csv_logs

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--data_dir", help="the path of the data directory.",
                        nargs='?', required=True)
    parser.add_argument("-q", "--questions", help="a sequence of question names.",
                        nargs='+', default=None)
    parser.add_argument('-f', "--offline_refactoring", action='store_true', default=False,
                        help="enable offline refactoring.")
    parser.add_argument('-o', "--online_refactoring", action='store_true', default=False,
                        help="enable online refactoring.")
    parser.add_argument('-b', "--block_repair", action='store_true', default=False,
                        help="enable block repair.")

    parser.add_argument("-s", "--sampling_rates", help="a sequence of sampling rates.",
                        nargs='+', type=int, default=[0, 20, 40, 60, 80, 100])
    parser.add_argument("-e", "--exp_num", help="the number of experiemnts for each sampling rate.",
                        nargs='?', type=int, default=1)

    parser.add_argument("-m", "--mutation", help="allow structure mutation.",
                        action="store_true", default=False)
    parser.add_argument("-c", "--cmb_log", help="combine log files into one.",
                        action="store_true", default=False)
    parser.add_argument("-y", "--oro_json", help="only do only refactoring and store the results.",
                        action="store_true", default=False)

    args = parser.parse_args()

    sr_list = args.sampling_rates
    if any(sr < 0 or sr > 100 for sr in sr_list):
        print("Illegal --sampling_rates.")
        exit(0)

    exp_time = args.exp_num
    if exp_time <= 0:
        print("Illegal --exp_num.")
        exit(0)

    if args.offline_refactoring and args.online_refactoring:
        print("-f and -o are mutually exclusive.")
        exit(0)

    if not (args.offline_refactoring or args.online_refactoring or args.block_repair or args.cmb_log or args.online_refactoring_only):
        print("-f, -o, -b, -c, -y should at least choose one.")
        exit(0)

    if args.oro_json:
        oro_dataset(args.data_dir, args.questions, sr_list, exp_time)
        exit(0)

    if args.offline_refactoring:
        for sr in sr_list:
            if sr == 0 or sr == 100:  # No repetitions since no real sampling
                ofl_refactor(args.data_dir, args.questions, sampling_rate=sr, exp_idx=0)
            else:
                for exp_idx in range(exp_time):  # Number of repetitions, for random sample
                    ofl_refactor(args.data_dir, args.questions, sampling_rate=sr, exp_idx=exp_idx)

    if args.block_repair:
        repair_dataset(args.data_dir, args.questions, args.offline_refactoring, args.online_refactoring, sr_list, exp_time, True, args.mutation)

    if args.cmb_log:
        if args.online_refactoring:
            cmb_csv_logs(args.data_dir, "online")
        elif args.offline_refactoring:
            cmb_csv_logs(args.data_dir, "offline")
        else:
            cmb_csv_logs(args.data_dir, "norefactor")

