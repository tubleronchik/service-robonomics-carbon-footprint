FROM python:3.8
COPY requirements.txt requirements.txt 
RUN /bin/bash -c 'curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | bash -s -- -y'
RUN /bin/bash -c 'source $HOME/.cargo/env; rustup default nightly; python3 -m pip install -r requirements.txt'
COPY . .
CMD ["python3", "./main.py"]