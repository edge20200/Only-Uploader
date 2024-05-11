FROM alpine:latest

# Install bash
RUN apk add --no-cache bash

# Add mono repo and mono
RUN apk add --no-cache mono --repository http://dl-cdn.alpinelinux.org/alpine/edge/testing

# Install requirements
RUN  apk add --no-cache --upgrade ffmpeg mediainfo python3 git py3-pip python3-dev g++ cargo mktorrent rust
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip3 install wheel

WORKDIR UploadAssistant

# Install python requirements
COPY requirements.txt .
RUN pip3 install -r requirements.txt

# Copy everything
COPY . .

# Set shell command alias
RUN echo 'alias l4g="/UploadAssistant/upload.py"' >> /root/.bashrc

# Start container and tail to keep container running
CMD ["/bin/bash", "-c", "tail -f /dev/null"]
