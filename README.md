# Refactory: Re-factoring based Program Repair applied to Programming Assignments
## What is Refactory
Refactory is a fully automated tool for generating real-time program repairs of buggy student programs, given one or more correct/reference programs. 

This is achieved by first re-factoring all available correct solutions to semantically equivalent solutions. Given an incorrect program, we match the program with the closest matching refactored program based on its control flow structure. Subsequently, we infer the input-output specifications of the incorrect program's basic blocks from the executions of the correct program's aligned basic blocks. Finally, these specifications are used to modify the blocks of the incorrect program via search-based synthesis.


## Contributors:
### Authors
Yang Hu, Umair Z. Ahmed, Sergey Mechtaev, Ben Leong, Abhik Roychoudhury

### Principal Investigator
Abhik Roychoudhury

### Developers
Yang Hu, Umair Z. Ahmed

## Publication
If you use any part of our Refactory tool or data present in this repository, then please do cite our [ASE-2019 Refactory paper](https://ieeexplore.ieee.org/abstract/document/8952522).

	@inproceedings{yang2019refactory,
        title={Re-factoring based Program Repair applied to Programming Assignments},
        author={Hu, Yang and Ahmed, Umair Z. and Mechtaev, Sergey and Leong, Ben and Roychoudhury, Abhik},
        booktitle={2019 34th IEEE/ACM International Conference on Automated Software Engineering (ASE)},
        pages={388--398},
        year={2019},
        organization={IEEE/ACM}
    }


## Dataset
The `data.zip` archive contains 2442 correct and 1783 buggy program attempts by 361 undergraduate students crediting an introduction to Python programming course at NUS (National University of Singapore). This dataset of 5 programming assignments is described in Section-V and Table-II of our [ASE-2019 Refactory paper](https://ieeexplore.ieee.org/abstract/document/8952522). 

Refactory tool expects the following inputs:
1. `Test-Suite`: Collection of input (`input_x.txt`) and its corresponding excepted output (`output_x.txt`). 
2. `reference.py`: The reference (correct) implementation provided by instructor, that passes the complete test-suite.
3. `correct_abc.py`: Correct program attempts by students, that passes all the test-cases.
4. `wrong_xyz.py`: Buggy program attempts by students, which fails on one or more test-cases.
5. `global.py`: Instructor provided imports and global function/variable declarations (if any).

Given these inputs, Refactory attempts to repair all buggy programs by inferring input-output specification from closest aligned (refactored) correct programs. These data data input files should be organized in the folder structure described below. Please refer to the 5 programming assignments present within `data.zip` for example.

```
|-data
    |-question_xxx
    |    |-ans
    |    |   |-input_xxx.txt
    |    |   |-output_xxx.txt
    |    |   |-...
    |    |   
    |    |-code
    |    |   |-reference
    |    |   |   |-reference.py
    |    |   |
    |    |   |-correct
    |    |   |   |-sub_xxxxxxx.py
    |    |   |   |-...
    |    |   |
    |    |   |-wrong
    |    |   |   |-sub_xxxxxxx.py
    |    |   |   |-... 
    |    |   |
    |    |   |-global.py   
    |    
    |-...
```

## Setup
### Extract Dataset
`unzip data.zip`

### Install Ubuntu/Debian packages
`sudo apt-get install python3 python3-pip`

### Install Python packages
Refactory is implemented in Python 3.7. The file `requirements.txt` lists the python packages, along with their specific version number, required by Refactory. We recommend using Anaconda-3 package distribution to maintain the package dependencies. 

`conda install --file requirements.txt`

Alternatively, `pip3` can be used, followed by manually ensuring that the dependencies are met.

`pip3 install -r requirements.txt`

### Docker environment

As an alternate to setting up the Ubuntu/Debian and Python packages manually, the same environment can be obtained by building a docker image based on `docker/Dockerfile`.

`sudo docker build -t refactory ./docker/`


## Running Refactory
Refactory tool is invoked using the command line interface offered by run.py.  For example, the below command runs Refactory on all buggy programs of `question_1` in the `./data` directory, with online refactoring, structure mutation, block repair phase enabled, and 100% sampling rate of correct programs.

`python3 run.py -d ./data -q question_1 -s 100 -o -m -b` 

### Command line arguments 
- `-d` flag specifies the path of data directory
- `-q` flag specifies the question (folder) name within data directory
- `-s` flag specifies the sampling rate. With `-s 0` option, only the instructor provided reference program is used to repair buggy student programs. `-s 100` option indicates that 100% of correct student programs (along with the instructor provided reference program) are used.
- `-o` flag enables online refactoring phase to generate new semantically equivalent correct programs, as described in Section-III of our [ASE-2019 Refactory paper](https://ieeexplore.ieee.org/abstract/document/8952522).
- `-f` flag applies the refactoring rules on all correct programs in an offline phase. During the online phase, the closest aligned refactored program is chosen for repair. Note that our implementation does not support  online and offline (`-o` and `-f` flags) simultaneously. 
- `-m` flag enables structure mutation phase, where the control flow structure of buggy program is mutated to match the closest refactored correct program. This phase occurs only if no refactored program with an exact control flow match is found, after the refactoring phase (`-o` or `-f` flag). This phase is described in Section-III of our [ASE-2019 Refactory paper](https://ieeexplore.ieee.org/abstract/document/8952522). 
- `-b` flag enables the block repair phase, where blockwise repair of buggy programs is performed by synthesizing a patch based on blockwise input-output specification of aligned (refactored) correct program. This phase is described in Section-IV of our [ASE-2019 Refactory paper](https://ieeexplore.ieee.org/abstract/document/8952522). 

### Output logs
After the completion of a run by Refactory tool, the intermediate results such as repaired program, time-taken, relative patch size, etc are logged into a csv file `./data/question_x/refactory_*.csv`. 
Where, * is either 'online', 'offline', or 'norefactor' depending of whether Refactory tool was invoked with `-o`, `-f` or neither of these two flags, respectively. 

Logs of individual questions, generated under the same settings, can be collated through use of `-c` flag. 
