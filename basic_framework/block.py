# Developers:   Yang Hu, et al.
# Email:    huyang0905@gmail.com

from basic_framework.statement import *


def is_pass_block(bb):
    line_list = bb.split("\n")[:-1]
    if len(line_list) == 1:
        token_list = get_token_list(bb)
        for token in token_list:
            if token.string == "pass":
                return True
    return False


def is_empty_block(bb):
    return len(bb) == 0 or is_pass_block(bb)