FROM nvcr.io/nvidia/l4t-ml:r36.2.0-py3

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /workspace

# System packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-tk \
    && rm -rf /var/lib/apt/lists/*

# Python packages
RUN python3 -m pip install --upgrade pip

RUN python3 -m pip install --no-cache-dir --no-deps \
    ultralytics \
    pyserial

RUN python3 -m pip install --no-cache-dir \
    pyyaml \
    requests \
    pillow \
    scipy \
    matplotlib \
    tqdm \
    psutil \
    pandas \
    seaborn
    
# GStreamer packages for video capture and processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    v4l-utils \
    && rm -rf /var/lib/apt/lists/*

CMD ["/bin/bash"]
