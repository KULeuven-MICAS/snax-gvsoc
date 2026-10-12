# snax-gvsoc development container.
#
# Holds GVSoC's build tools, its Python packages, snax_cluster's RISC-V
# toolchain and zsh. GVSoC itself is NOT in the image: mount this repo at
# /work and build it there, so edits and build output stay on the host.
#
# Two stages, as in snax_cluster's util/container/Dockerfile: pixi installs the
# locked toolchain in the first, and only the environment is copied into the
# second, at the same path, since a conda environment has its path built in.
#
# Build (from the repo root; container/toolchain/pixi.lock must exist):
#   docker build -t ghcr.io/kuleuven-micas/snax-gvsoc:main container
# Run:
#   podman run --rm -it -v "$PWD":/work ghcr.io/kuleuven-micas/snax-gvsoc:main

########################################################################
# Stage 1: the RISC-V toolchain, installed with pixi
########################################################################
FROM ubuntu:24.04 AS toolchain

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

ARG PIXI_VERSION=0.81.0
ARG PIXI_SHA256=7aa3ec39aecceff9062fa2ed4d42cbaa0bdc25ddea727d048e061cf188d434f6
RUN curl -fsSL --retry 5 -o /tmp/pixi.tar.gz \
        "https://github.com/prefix-dev/pixi/releases/download/v${PIXI_VERSION}/pixi-x86_64-unknown-linux-musl.tar.gz" \
    && echo "${PIXI_SHA256}  /tmp/pixi.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/pixi.tar.gz -C /usr/local/bin pixi \
    && rm /tmp/pixi.tar.gz

# clang, lld, llvm-tools, clang-format 21.1.6 and bender 0.28.2: the exact
# builds snax_cluster's pixi.lock holds (see toolchain/pixi.toml).
COPY toolchain/pixi.toml toolchain/pixi.lock /opt/toolchain/
RUN cd /opt/toolchain && pixi install --locked

########################################################################
# Stage 2: the image
########################################################################
FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive

# Host compiler and build tools for GVSoC, plus zsh.
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
        zsh \
    && rm -rf /var/lib/apt/lists/*

COPY --from=toolchain /opt/toolchain/.pixi/envs/default /opt/toolchain/.pixi/envs/default

# Python packages in a venv, so nothing fights the system Python.
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# zsh with oh-my-zsh and the autosuggestions plugin, as snax_cluster's image
# had them (53efdeb), but at fixed versions and with oh-my-zsh's update
# check off, so a rebuild gives the same shell.
ARG OMZ_COMMIT=083c339e0622bfc144b66ebf1a2e8dbe7d2ada0d
ARG ZSH_AUTOSUGGESTIONS_TAG=v0.7.1
RUN git init -q /root/.oh-my-zsh \
    && git -C /root/.oh-my-zsh fetch -q --depth 1 https://github.com/ohmyzsh/ohmyzsh.git "$OMZ_COMMIT" \
    && git -C /root/.oh-my-zsh -c advice.detachedHead=false checkout -q FETCH_HEAD \
    && sed "s|^# zstyle ':omz:update' mode disabled|zstyle ':omz:update' mode disabled|" \
        /root/.oh-my-zsh/templates/zshrc.zsh-template > /root/.zshrc \
    && git clone -q --depth 1 --branch "$ZSH_AUTOSUGGESTIONS_TAG" \
        https://github.com/zsh-users/zsh-autosuggestions.git \
        /root/.oh-my-zsh/custom/plugins/zsh-autosuggestions \
    && echo "source ~/.oh-my-zsh/custom/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh" >> /root/.zshrc \
    && chsh -s /usr/bin/zsh

# The toolchain goes last on PATH, so nothing in it can shadow the host tools
# GVSoC builds with.
ENV PATH=/opt/venv/bin:$PATH:/opt/toolchain/.pixi/envs/default/bin \
    GVSOC_WORKDIR=/work/build

# The repo is bind-mounted and owned by the host user.
RUN git config --system --add safe.directory '*'

WORKDIR /work
CMD ["zsh"]
