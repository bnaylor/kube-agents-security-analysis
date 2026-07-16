#!/usr/bin/env bash
set -euo pipefail

# Path to the onedoc binary used to build the Google Doc.
# Override with ONEDOC_BIN; defaults to whatever `onedoc` is on PATH.
onedoc="${ONEDOC_BIN:-onedoc}"
d="${1:-$(date +"%Y-%m-%d")}"
datestr=$(date +"%B %d, %Y")
gdate=$(date -u +'%Y-%m-%dT%H:%M:%SZ')

# Configurable paths with defaults based on $HOME/src
SRC_DIR="${SRC_DIR:-${HOME}/src}"
base_dir="${ANALYSIS_DIR:-${SRC_DIR}/kube-agents-security-analysis}"
target_dir="${base_dir}/${d}"
title="Kube Agents Security Analysis ${d}"

echo "Generating ${title}..."

mkdir -p "${target_dir}"

# Copy template toc.md if not present in target directory
if [ ! -f "${target_dir}/toc.md" ]; then
    if [ -f "${base_dir}/toc.md" ]; then
        cp "${base_dir}/toc.md" "${target_dir}/"
    else
        cat << TOC_EOF > "${target_dir}/toc.md"
# Kube Agents Security Analysis - __DATE__

**Date:** [__DATE__](google-date:__GDATE__)

This is a point-in-time analysis of the security posture, risks, and threat modelling for kube_agents.
TOC_EOF
    fi
fi

# Substitute date markers in target toc.md
perl -pi -e "s/__DATE__/${datestr}/" "${target_dir}/toc.md" 2>/dev/null || true
perl -pi -e "s/__GDATE__/${gdate}/" "${target_dir}/toc.md" 2>/dev/null || true

# Strip onedoc metadata from toc.md if previously linked
sed -i '/onedoc_/d' "${target_dir}/toc.md" 2>/dev/null || true

# Create or get main Google Doc from TOC
doc_output=$(${onedoc} create-gdoc --from-md "${target_dir}/toc.md" --title "${title}" 2>&1 || true)
url=$(echo "${doc_output}" | grep -o -E 'https://docs\.google\.com/document/d/[a-zA-Z0-9_-]+' | head -n 1 || echo "")

if [ -z "${url}" ]; then
    echo "Error creating/resolving Google Doc:"
    echo "${doc_output}"
    exit 1
fi

# Helper to add tabs to the Google Doc
create_tab() {
    local doc_url="$1"
    local md_file="$2"
    local tab_title="$3"

    if [ -f "${md_file}" ]; then
        # Strip onedoc link metadata if previously linked
        sed -i '/onedoc_/d' "${md_file}" 2>/dev/null || true
        echo "Creating tab '${tab_title}' from ${md_file}..."
        ${onedoc} create-gdoc-tab "${doc_url}" --from-md "${md_file}" --title "${tab_title}" 2>&1 || true
    else
        echo "Warning: ${md_file} not found. Skipping tab creation for '${tab_title}'."
    fi
}

create_tab "${url}" "${target_dir}/architectural_summary.md" "Architectural and Security Summary"
create_tab "${url}" "${target_dir}/threat_model.md" "Threat Model"
create_tab "${url}" "${target_dir}/devteam_token_refresh_analysis.md" "DevTeam Token Refresh Mechanism (bug)"
create_tab "${url}" "${target_dir}/platform_agent_least_privilege_analysis.md" "Least Privilege Analysis (Platform Agent)"
create_tab "${url}" "${target_dir}/webhook_security_analysis.md" "Webhook Analysis"
create_tab "${url}" "${target_dir}/yolo_security_synthesis.md" "Normal mode vs YOLO mode"

echo ""
echo "================================================================================"
echo "Google Doc successfully created: ${url}"
echo "================================================================================"
