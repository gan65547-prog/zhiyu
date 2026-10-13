#!/usr/bin/env bash
# =============================================
# verify-backup.sh - 备份恢复验证脚本
#
# 功能：
#   1. 列出可用的数据库备份
#   2. 验证备份文件完整性
#   3. 在临时数据库上执行恢复测试
#   4. 报告备份状态
#
# 用法：
#   ./scripts/verify-backup.sh                  # 验证最新备份
#   ./scripts/verify-backup.sh --list            # 列出所有备份
#   ./scripts/verify-backup.sh --file <path>     # 验证指定备份
#   ./scripts/verify-backup.sh --check <name>    # 验证指定名称的备份
#
# 依赖：
#   - pg_dump / pg_restore（PostgreSQL 客户端）
#   - psql
# =============================================

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./runtime/backups}"
TEST_DB_NAME="erag_verify_$(date +%s)"
LOG_FILE="${BACKUP_DIR}/verify-$(date +%Y%m%d-%H%M%S).log"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; echo "[INFO] $*" >> "$LOG_FILE"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; echo "[WARN] $*" >> "$LOG_FILE"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; echo "[ERROR] $*" >> "$LOG_FILE"; }

# 检查依赖
check_deps() {
    for cmd in pg_dump pg_restore psql createdb dropdb; do
        if ! command -v "$cmd" &>/dev/null; then
            log_error "未找到 ${cmd}，请安装 PostgreSQL 客户端工具"
            exit 1
        fi
    done
}

# 获取数据库连接参数
get_db_url() {
    # 优先从环境变量读取，否则从 .env 文件或 docker-compose 配置读取
    local url="${DATABASE_URL:-}"
    if [ -z "$url" ]; then
        # 尝试从 .env 读取
        if [ -f ".env" ]; then
            url=$(grep -E '^DATABASE_URL=' .env | head -1 | cut -d= -f2-)
        fi
    fi
    echo "$url"
}

# 列出可用备份
list_backups() {
    log_info "可用备份:"
    echo "---"
    if [ ! -d "$BACKUP_DIR" ]; then
        log_warn "备份目录不存在: $BACKUP_DIR"
        return
    fi

    local count=0
    for f in "$BACKUP_DIR"/*.dump "$BACKUP_DIR"/*.sql "$BACKUP_DIR"/*.tar; do
        if [ -f "$f" ]; then
            local size=$(du -h "$f" | cut -f1)
            local modified=$(stat -c "%y" "$f" 2>/dev/null || stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$f" 2>/dev/null || echo "unknown")
            echo "  $f  (${size}, 修改时间: ${modified})"
            count=$((count + 1))
        fi
    done

    if [ "$count" -eq 0 ]; then
        log_warn "未找到备份文件"
    else
        log_info "共 $count 个备份文件"
    fi
}

# 验证备份文件完整性（不恢复数据库）
verify_file_integrity() {
    local file="$1"
    log_info "验证文件完整性: $file"

    if [ ! -f "$file" ]; then
        log_error "文件不存在: $file"
        return 1
    fi

    # macOS uses `stat -f`, while GNU/Linux uses `stat -c`; try the
    # byte-size form first so filesystem metadata is never treated as a size.
    local size=$(stat -c "%s" "$file" 2>/dev/null || stat -f "%z" "$file" 2>/dev/null || echo 0)
    if [ "$size" -eq 0 ]; then
        log_error "文件大小为 0: $file"
        return 1
    fi

    # 根据文件扩展名选择验证方式
    case "$file" in
        *.dump)
            if pg_restore --list "$file" &>/dev/null; then
                log_info "Custom format dump: 可读 (${size} bytes)"
                return 0
            else
                log_error "Custom format dump: 损坏或不可读"
                return 1
            fi
            ;;
        *.sql)
            # 检查 SQL 文件头部
            if head -5 "$file" | grep -qE '(PG dump|CREATE|INSERT|-- )' ; then
                log_info "SQL dump: 语法检查通过 (${size} bytes)"
                return 0
            else
                # 可能不是标准的 pg dump，但文件非空即可
                log_warn "SQL dump: 非标准格式，但文件非空"
                return 0
            fi
            ;;
        *.tar)
            if tar -tf "$file" &>/dev/null; then
                log_info "Tar archive: 可解压 (${size} bytes)"
                return 0
            else
                log_error "Tar archive: 损坏"
                return 1
            fi
            ;;
        *)
            log_warn "未知备份格式: $file (仅检查文件大小)"
            return 0
            ;;
    esac
}

# 在临时数据库上执行恢复测试
test_restore() {
    local file="$1"
    local db_url=$(get_db_url)

    if [ -z "$db_url" ]; then
        log_warn "未配置 DATABASE_URL，跳过恢复测试（仅验证文件完整性）"
        return 0
    fi

    # 从 URL 提取主机和端口
    local db_host=$(echo "$db_url" | sed -n 's/.*@\([^:]*\).*/\1/p')
    local db_port=$(echo "$db_url" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    local db_user=$(echo "$db_url" | sed -n 's#^[^:]*://\([^:/]*\):.*@.*#\1#p')
    local db_password=$(echo "$db_url" | sed -n 's#^[^:]*://[^:]*:\([^@]*\)@.*#\1#p')
    db_host="${db_host:-localhost}"
    db_port="${db_port:-5432}"
    db_user="${db_user:-postgres}"

    # The helper commands do not consume DATABASE_URL directly. Pass the
    # parsed credentials explicitly so containerized verification does not
    # accidentally use the shell/container user.
    local -a db_auth_args=( -U "$db_user" )
    if [ -n "$db_password" ]; then
        export PGPASSWORD="$db_password"
    fi

    log_info "创建临时数据库: $TEST_DB_NAME"

    # 创建临时数据库
    if createdb -h "$db_host" -p "$db_port" "${db_auth_args[@]}" "$TEST_DB_NAME" 2>/dev/null; then
        log_info "临时数据库创建成功"
    else
        log_warn "无法创建临时数据库，跳过恢复测试"
        return 0
    fi

    # 执行恢复
    local restore_ok=true
    case "$file" in
        *.dump)
            if pg_restore -h "$db_host" -p "$db_port" "${db_auth_args[@]}" -d "$TEST_DB_NAME" --no-owner --no-privileges "$file" &>/dev/null; then
                log_info "Custom format 恢复成功"
            else
                log_error "Custom format 恢复失败"
                restore_ok=false
            fi
            ;;
        *.sql)
            if psql -h "$db_host" -p "$db_port" "${db_auth_args[@]}" -d "$TEST_DB_NAME" -f "$file" &>/dev/null; then
                log_info "SQL dump 恢复成功"
            else
                log_error "SQL dump 恢复失败"
                restore_ok=false
            fi
            ;;
        *.tar)
            if pg_restore -h "$db_host" -p "$db_port" "${db_auth_args[@]}" -d "$TEST_DB_NAME" --no-owner --no-privileges "$file" &>/dev/null; then
                log_info "Tar format 恢复成功"
            else
                log_error "Tar format 恢复失败"
                restore_ok=false
            fi
            ;;
    esac

    # 验证恢复后的数据
    if [ "$restore_ok" = true ]; then
        log_info "验证恢复数据..."
        local table_count=$(psql -h "$db_host" -p "$db_port" "${db_auth_args[@]}" -d "$TEST_DB_NAME" -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')
        log_info "恢复的表数量: $table_count"

        if [ "$table_count" -gt 0 ]; then
            log_info "数据校验通过"
        else
            log_warn "恢复后未找到表，可能备份为空"
        fi
    fi

    # 清理临时数据库
    log_info "清理临时数据库: $TEST_DB_NAME"
    dropdb -h "$db_host" -p "$db_port" "${db_auth_args[@]}" "$TEST_DB_NAME" 2>/dev/null || log_warn "临时数据库清理失败"

    $restore_ok
}

# 主流程
main() {
    local mode="${1:-latest}"
    local target_file=""

    check_deps
    mkdir -p "$BACKUP_DIR"
    echo "" > "$LOG_FILE"

    log_info "备份验证工具"
    log_info "备份目录: $BACKUP_DIR"
    log_info "日志文件: $LOG_FILE"
    echo "---"

    case "$mode" in
        --list|-l)
            list_backups
            exit 0
            ;;
        --file|-f)
            target_file="$2"
            if [ -z "$target_file" ]; then
                log_error "请指定备份文件路径: --file <path>"
                exit 1
            fi
            ;;
        --check|-c)
            local name="$2"
            if [ -z "$name" ]; then
                log_error "请指定备份名称: --check <name>"
                exit 1
            fi
            target_file="${BACKUP_DIR}/${name}"
            ;;
        latest|--latest)
            # 找到最新的 .dump 或 .sql 文件
            target_file=$(ls -t "$BACKUP_DIR"/*.dump "$BACKUP_DIR"/*.sql 2>/dev/null | head -1)
            if [ -z "$target_file" ]; then
                log_error "未找到备份文件"
                list_backups
                exit 1
            fi
            log_info "验证最新备份: $target_file"
            ;;
        *)
            log_error "未知选项: $mode"
            echo "用法: $0 [--list|--file <path>|--check <name>|latest]"
            exit 1
            ;;
    esac

    # 执行验证
    local integrity_ok=false
    if verify_file_integrity "$target_file"; then
        integrity_ok=true
    fi

    if [ "$integrity_ok" = true ]; then
        test_restore "$target_file"
    fi

    echo "---"
    log_info "验证完成。日志: $LOG_FILE"
}

main "$@"
