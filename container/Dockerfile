# snax-gvsoc development container.
#
# Holds the compilers, Python packages and the two prebuilt RISC-V toolchains.
# GVSoC itself is NOT in the image: mount the snax-gvsoc repo at /work and
# build it there, so edits and build output stay on the host.
#
# Build (from the repo root):
#   docker build -t ghcr.io/kuleuven-micas/snax-gvsoc:gvs1 container
# Run:
#   podman run --rm -it -v "$PWD":/work ghcr.io/kuleuven-micas/snax-gvsoc:gvs1

FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive

# Host compiler and build tools for GVSoC, plus what the downloads need.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        ccache \
        git \
        ca-certificates \
        curl \
        xz-utils \
        python3 \
        python3-venv \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# RISC-V GCC 14.2 (rv64, newlib): compiles the GVSoC tutorial programs.
# Same release the GVSoC Makefile downloads in its `riscv` target.
ARG RISCV_GCC_URL=https://github.com/riscv-collab/riscv-gnu-toolchain/releases/download/2025.01.17/riscv64-elf-ubuntu-22.04-gcc-nightly-2025.01.17-nightly.tar.xz
ARG RISCV_GCC_SHA256=d676a5cbff9160e40dbc0092b716d6f63ad66302bb8d0de9ef78bb007f14a340
RUN curl -fsSL --retry 5 -o /tmp/riscv.tar.xz "$RISCV_GCC_URL" \
    && echo "$RISCV_GCC_SHA256  /tmp/riscv.tar.xz" | sha256sum -c - \
    && tar -xJf /tmp/riscv.tar.xz -C /opt \
    && rm /tmp/riscv.tar.xz

# Snitch LLVM 0.12.0 (clang 12.0.1, rv32 + Snitch extensions): compiles the
# snitch_cluster runtime and programs.
ARG SNITCH_LLVM_URL=https://github.com/pulp-platform/llvm-project/releases/download/0.12.0/riscv32-pulp-llvm-ubuntu2004-0.12.0.tar.gz
ARG SNITCH_LLVM_SHA256=70534a8946cad71698be9d7bf4edcc0c1b322aabfe6c47a416e82a035c627451
RUN curl -fsSL --retry 5 -o /tmp/llvm.tar.gz "$SNITCH_LLVM_URL" \
    && echo "$SNITCH_LLVM_SHA256  /tmp/llvm.tar.gz" | sha256sum -c - \
    && mkdir -p /opt/snitch-llvm \
    && tar -xzf /tmp/llvm.tar.gz -C /opt/snitch-llvm --strip-components=1 \
    && rm /tmp/llvm.tar.gz

# Bender 0.27.1: the snitch_cluster makefiles call it to locate the register
# tool when they generate the runtime headers.
ARG BENDER_URL=https://github.com/pulp-platform/bender/releases/download/v0.27.1/bender-0.27.1-x86_64-linux-gnu-ubuntu18.04.tar.gz
ARG BENDER_SHA256=ddc7c7c81685194e2a9a1e69e763f8e4e7077515309a66c1ae2219bc0c0f8b81
RUN curl -fsSL --retry 5 -o /tmp/bender.tar.gz "$BENDER_URL" \
    && echo "$BENDER_SHA256  /tmp/bender.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/bender.tar.gz -C /usr/local/bin bender \
    && rm /tmp/bender.tar.gz

# Python packages in a venv, so nothing fights the system Python.
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# The Snitch LLVM directory goes last on PATH: its makefiles need clang-format
# from there, and last place keeps it from shadowing any host tool. The
# compiler itself is picked through LLVM_BINROOT.
ENV PATH=/opt/venv/bin:/opt/riscv/bin:$PATH:/opt/snitch-llvm/bin \
    LLVM_BINROOT=/opt/snitch-llvm/bin \
    GVSOC_WORKDIR=/work/build

# The repo is bind-mounted and owned by the host user.
RUN git config --system --add safe.directory '*'

WORKDIR /work
CMD ["/bin/bash"]