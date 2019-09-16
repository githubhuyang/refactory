# Refactory: Re-factoring based Program Repair applied to Programming Assignments
## What is Refactory
Refactory is a fully automated approach for generating student program repairs in real-time. It refactors all available correct solutions to semantically equivalent solutions in an online/offline phase. Those solutions are then used to repair the incorrect solutions via search-based program synthesis.

## Authors
Yang Hu, Umair Z. Ahmed, Sergey Mechtaev, Ben Leong, Abhik Roychoudhury

If you use Refactory in your research project, please include the following citation:

	@inproceedings{yang2019refactory,
        title={Re-factoring based Program Repair applied to Programming Assignments},
        author={Hu, Yang and Ahmed, Umair Z. and Mechtaev, Sergey and Leong, Ben and Roychoudhury, Abhik},
        booktitle={The 34th IEEE/ACM International Conference on Automated Software Engineering (ASE 2019)},
        year={2019},
        organization={IEEE/ACM}
    }

## Principal Investigator
Abhik Roychoudhury

## Developers
Yang Hu, Umair Z. Ahmed

## Usage
### Data Format
Data directory contains all inputs of Refactory, including test-suite, student submissions (correct or buggy) and referene solutions. Please arranges those items in the following directory tree structure.
```
|-data
    |-question_xxx
    |    |-ans
    |    |   |-input_xxx.txt
    |    |   |-output_xxx.txt
    |    |   |-...
    |    |   
    |    |-code
    |        |-correct
    |        |   |-sub_xxxxxxx.py
    |        |   |-...
    |        |
    |        |-wrong
    |            |-sub_xxxxxxx.py
    |            |-...
    |            
    |
    |-...
```
`ans` directory contains the whole test-suite, which is arranged as a sequence of input-output file pairs. `code/correct` directory contains all correct (i.e., pass all test cases) submissions, while `code/wrong` contains incorrect ones. `global.py`

### Run Refactory
#### Experimental Environment Setup
Refactory is implemented in Python 3.7. Although there are various Python distributions available online, we recommend using Anaconda 3, which has preinstalled commonly-used Python software packages. Then use `pip` to install residucal software packages to Anaconda.

`pip install psutil zss autopep8 python-Levenshtein astunparse prettytable apted fastcache`

Besides manually deploying the experimental environment, you can setup the environment in docker by building a docker image based on `docker/Dockerfile`.

`sudo docker build -t refactory ./docker/`

#### Refactory's CLI

##### General Flags
Refactory has a command line interface in run.py. In general, you need to declare the path of data directory via `-d`, the question name via `-q`, and a list of sampling rate via `-s`. Besides, add `-o` to enable online refactoring, add `-f` to enable offline refacotirng，add `-b` to enable block repair, and add `-m` to enable structure mutation. Please kindly note that Refactory currently does not support to enable both online and offline refactoring. For example, consider the following command.

`python run.py -d ./data -q question_123 -s 100 -o -m -b` 

Those flags indicate you want to run Refactory with 100% sampling rate, online refactoring, and structure mutaion and block repair to fix all buggy programs in question_123 in the `./data` directory.

##### Flag for Log Generation
By default, Refactory logs repairs, time consumotion, relative patch size and etc into a csv file for each question. The csv file name is refactory_*.csv, where * should be 'online', 'offline', or 'norefactor'. To combine logs for different questions, you can use `-c` flag to ask Refactory to combine all csv files generated under the same setting into one csv file.