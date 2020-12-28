FROM amazonlinux:latest

ENV PIPENV_VENV_IN_PROJECT=true
RUN yum update -y
RUN yum install zlib-devel libffi-devel bzip2-devel openssl-devel ncurses-devel sqlite-devel readline-devel tk-devel gdbm-devel libuuid-devel xz-devel tar gzip gcc make -y
# RUN yum install python3 -y
RUN curl -O https://www.python.org/ftp/python/3.8.7/Python-3.8.7.tgz && tar -zxf Python-3.8.7.tgz && cd Python-3.8.7 && ./configure && make && make altinstall
RUN python3.8 --version
RUN pip3.8 install pipenv
WORKDIR /var/task
RUN pipenv install --python 3.8