#!/usr/bin/env bash
set -euo pipefail

# Configurable paths with defaults based on $HOME/src
SRC_DIR="${SRC_DIR:-${HOME}/src}"
KUBE_AGENTS_DIR="${KUBE_AGENTS_DIR:-${SRC_DIR}/kube-agents}"
ANALYSIS_DIR="${ANALYSIS_DIR:-${SRC_DIR}/kube-agents-security-analysis}"

d="${1:-$(date +"%Y-%m-%d")}"

echo "================================================================================"
echo "🤖 Automated Security Analysis for ${d}"
echo "  Target Repository : ${KUBE_AGENTS_DIR}"
echo "  Analysis Directory: ${ANALYSIS_DIR}/${d}"
echo "================================================================================"

if [ ! -d "${KUBE_AGENTS_DIR}" ]; then
    echo "Error: Repository directory ${KUBE_AGENTS_DIR} does not exist."
    exit 1
fi

mkdir -p "${ANALYSIS_DIR}/${d}"

PROMPT="Execute the 'generate-security-analysis-report' skill for target date '${d}'. Perform a complete security audit of the repository located at '${KUBE_AGENTS_DIR}', write all 6 markdown report files directly to '${ANALYSIS_DIR}/${d}/', and execute '${ANALYSIS_DIR}/generate.sh ${d}' to build the tabbed Google Doc."

if command -v agentapi >/dev/null 2>&1; then
    echo "Launching agent via agentapi..."
    agentapi new-conversation --title="Automated Security Analysis ${d}" "${PROMPT}"
else
    echo "agentapi CLI not found in PATH. Please invoke the skill directly in your agent session with:"
    echo "  ${PROMPT}"
    exit 1
fi
