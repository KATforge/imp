FROM ghcr.io/charmbracelet/vhs:latest

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-pip python3-venv \
      git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
ENV HATCH_BUILD_HOOKS_ENABLE=false
ENV HATCH_VCS_PRETEND_VERSION=0.0.0+demo
RUN SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0+demo \
    pip install --break-system-packages --no-cache-dir .

COPY demo/fake-claude /usr/local/bin/claude
COPY demo/fake-gh     /usr/local/bin/gh
COPY demo/setup-tidy.sh    /usr/local/bin/setup-tidy
COPY demo/setup-commit.sh  /usr/local/bin/setup-commit
COPY demo/setup-pr.sh      /usr/local/bin/setup-pr
COPY demo/setup-release.sh /usr/local/bin/setup-release
RUN chmod +x /usr/local/bin/claude /usr/local/bin/gh \
             /usr/local/bin/setup-tidy /usr/local/bin/setup-commit \
             /usr/local/bin/setup-pr   /usr/local/bin/setup-release

ENV IMP_AI_PROVIDER=claude
ENV IMP_AI_MODEL_FAST=stub
ENV IMP_AI_MODEL_SMART=stub
ENV PS1='\[\e[38;2;74;222;0m\]➜\[\e[0m\] \w \[\e[38;2;78;122;78m\]›\[\e[0m\] '
ENV TERM=xterm-256color

WORKDIR /vhs
