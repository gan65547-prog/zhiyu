#!/usr/bin/env bash
# =============================================================
# Version Helper Functions
#
# 用途：共享版本生成和标签处理逻辑
# 被其他部署脚本引用
# =============================================================

# 从标签中提取版本信息
extract_version_from_tag() {
    local tag="$1"

    # 支持两种格式：
    # staging-v2.0.21_202604211234_abc12345
    # release-v2.0.21_202604211234_abc12345

    if [[ "$tag" =~ ^(staging|release)-v([0-9]+\.[0-9]+\.[0-9]+)_([0-9]+)_([a-f0-9]+)$ ]]; then
        local stage="${BASH_REMATCH[1]}"
        local version="${BASH_REMATCH[2]}"
        local timestamp="${BASH_REMATCH[3]}"
        local git_sha="${BASH_REMATCH[4]}"

        echo "{\"stage\":\"$stage\",\"version\":\"$version\",\"timestamp\":\"$timestamp\",\"git_sha\":\"$git_sha\"}"
    else
        return 1
    fi
}

# 生成 staging tag
generate_staging_tag() {
    local version="$1"
    local timestamp=$(date +%Y%m%d%H%M)
    local git_sha=$(git rev-parse --short=8 HEAD)

    echo "staging-v${version}_${timestamp}_${git_sha}"
}

# 生成 production tag（从 staging tag）
generate_prod_tag_from_staging() {
    local staging_tag="$1"

    if [[ "$staging_tag" =~ ^staging-(v.*)$ ]]; then
        echo "release-${BASH_REMATCH[1]}"
    else
        return 1
    fi
}

# 格式化时间戳为可读格式
format_timestamp() {
    local timestamp="$1"

    # 将 202604211234 格式转换为 2026-04-21 12:34
    if [[ "$timestamp" =~ ^([0-9]{4})([0-9]{2})([0-9]{2})([0-9]{2})([0-9]{2})$ ]]; then
        echo "${BASH_REMATCH[1]}-${BASH_REMATCH[2]}-${BASH_REMATCH[3]} ${BASH_REMATCH[4]}:${BASH_REMATCH[5]}"
    else
        echo "$timestamp"
    fi
}

# 检查 tag 是否存在于远程
tag_exists_remote() {
    local tag="$1"

    git ls-remote origin "$tag" --exit-code >/dev/null 2>&1
}

# 检查本地 tag 是否存在
tag_exists_local() {
    local tag="$1"

    git rev-parse "$tag" >/dev/null 2>&1
}

# 导出函数供其他脚本使用
export -f extract_version_from_tag
export -f generate_staging_tag
export -f generate_prod_tag_from_staging
export -f format_timestamp
export -f tag_exists_remote
export -f tag_exists_local
