FROM ubuntu:18.10
MAINTAINER Yang Hu <huyang0905@gmail.com>

# Install basic dependencies
RUN apt-get update && apt-get install -y --no-install-recommends pkg-config git python-dev gcc wget vim zip ca-certificates

# Install anaconda3
RUN mkdir /home/huyang
RUN cd /home/huyang/ && wget --no-check-certificate https://repo.anaconda.com/archive/Anaconda3-2019.03-Linux-x86_64.sh && chmod 777 ./Anaconda3-2019.03-Linux-x86_64.sh && ./Anaconda3-2019.03-Linux-x86_64.sh -b -p /home/huyang/conda
RUN echo "export PATH=/home/huyang/conda/bin:$PATH" >> ~/.bashrc
RUN export PATH=/home/huyang/conda/bin:$PATH && pip install --upgrade pip && pip install psutil zss autopep8 python-Levenshtein astunparse prettytable apted fastcache

# Set workdir
WORKDIR /home/huyang
#RUN git clone https://github.com/githubhuyang/refactory.git

