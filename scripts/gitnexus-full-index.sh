#!/usr/bin/env bash
set -euo pipefail

export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export GITNEXUS_EMBEDDING_DEVICE="${GITNEXUS_EMBEDDING_DEVICE:-cpu}"
export GITNEXUS_EMBEDDING_THREADS="${GITNEXUS_EMBEDDING_THREADS:-2}"

if [[ -n "${GITNEXUS_PROXY:-}" ]]; then
  export HTTP_PROXY="$GITNEXUS_PROXY"
  export HTTPS_PROXY="$GITNEXUS_PROXY"
  export ALL_PROXY="$GITNEXUS_PROXY"
fi

mkdir -p logs/gitnexus

gitnexus --version
AGENT_ARG="--skip-agents-md"
if [[ "${GITNEXUS_UPDATE_AGENT_CONTEXT:-0}" == "1" ]]; then
  AGENT_ARG=""
fi

gitnexus analyze --force --embeddings --skills --verbose $AGENT_ARG \
  2>&1 | tee logs/gitnexus/v1.4.7-full-index.log

gitnexus status
gitnexus list
