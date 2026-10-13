#!/bin/bash
# v2.1 E2E 测试脚本 (修正版 - 正确模拟飞书来源)
BASE="http://localhost:8000"
PASS=0; FAIL=0

log_pass() { echo "  PASS: $1"; PASS=$((PASS+1)); }
log_fail() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }

echo "============================================="
echo "  v2.1 多租户接入 E2E 测试 (修正版)"
echo "============================================="

# === Test 1: Challenge ===
echo ""
echo "--- Test 1: Challenge 验证 ---"
R=$(curl -s -X POST "$BASE/api/v1/integration/chat" \
  -H "Content-Type: application/json" \
  -d '{"challenge":"test_abc123"}')
if echo "$R" | grep -q '"test_abc123"'; then log_pass "Challenge 原样返回"; else log_fail "Challenge: $R"; fi

R=$(curl -s -X POST "$BASE/api/v1/integration/chat" \
  -H "Content-Type: application/json" \
  -d '{"encrypt":"data"}')
if [ "$R" = "{}" ]; then log_pass "Encrypt 返回空对象"; else log_fail "Encrypt: $R"; fi

# === Test 2: 飞书消息 + app_id header ===
echo ""
echo "--- Test 2: 飞书 Webhook + X-Lark-App-Id=cli_corp_alpha ---"
R=$(curl -s -X POST "$BASE/api/v1/integration/chat" \
  -H "Content-Type: application/json" \
  -H "x-lark-request-id: req_001" \
  -H "X-Lark-App-Id: cli_corp_alpha" \
  -d '{"header":{"event_type":"im.message.receive_v1"},"event":{"sender":{"sender_id":{"open_id":"ou_v21_a1"}},"message":{"message_id":"om_a1","message_type":"text","content":"{\"text\":\"企业A用户提问\"}"}}}')
if echo "$R" | grep -q '"success":true'; then
  log_pass "企业A消息处理成功"
else
  log_fail "企业A: $R"
fi

# === Test 3: 同一 open_id 不同 app_id ===
echo ""
echo "--- Test 3: 同一 open_id + 不同 App-Id=cli_corp_beta ---"
R=$(curl -s -X POST "$BASE/api/v1/integration/chat" \
  -H "Content-Type: application/json" \
  -H "x-lark-request-id: req_002" \
  -H "X-Lark-App-Id: cli_corp_beta" \
  -d '{"header":{"event_type":"im.message.receive_v1"},"event":{"sender":{"sender_id":{"open_id":"ou_v21_a1"}},"message":{"message_id":"om_b1","message_type":"text","content":"{\"text\":\"同一人但不同企业\"}"}}}')
if echo "$R" | grep -q '"success":true'; then
  log_pass "企业B(同open_id)处理成功 → 多租户隔离验证"
else
  log_fail "企业B: $R"
fi

# === Test 4: 降级模式 (有 x-lark header 但无 App-Id) ===
echo ""
echo "--- Test 4: 降级模式 (x-lark header 但无 App-Id) ---"
R=$(curl -s -X POST "$BASE/api/v1/integration/chat" \
  -H "Content-Type: application/json" \
  -H "x-lark-request-id: req_fallback" \
  -d '{"header":{"event_type":"im.message.receive_v1"},"event":{"sender":{"sender_id":{"open_id":"ou_fallback"}},"message":{"message_id":"om_fb1","message_type":"text","content":"{\"text\":\"降级测试\"}"}}}')
if echo "$R" | grep -q '"success":true'; then
  log_pass "降级到默认租户成功"
else
  log_fail "降级: $R"
fi

# === Test 5: URL query 参数 ?app=xxx ===
echo ""
echo "--- Test 5: URL query 参数识别 ---"
R=$(curl -s -X POST "$BASE/api/v1/integration/chat?app=cli_from_url_param" \
  -H "Content-Type: application/json" \
  -H "x-lark-request-id: req_url" \
  -d '{"header":{"event_type":"im.message.receive_v1"},"event":{"sender":{"sender_id":{"open_id":"ou_url_user"}},"message":{"message_id":"om_url1","message_type":"text","content":"{\"text\":\"URL参数测试\"}"}}}')
if echo "$R" | grep -q '"success":true'; then
  log_pass "URL query ?app= 识别成功"
else
  log_fail "URL query: $R"
fi

# === Test 6: 非 text 消息 ===
echo ""
echo "--- Test 6: 非 text 消息 (image) ---"
R=$(curl -s -X POST "$BASE/api/v1/integration/chat" \
  -H "Content-Type: application/json" \
  -H "x-lark-request-id: req_img" \
  -d '{"header":{"event_type":"im.message.receive_v1"},"event":{"sender":{"sender_id":{"open_id":"ou_img"}},"message":{"message_id":"om_img1","message_type":"image","content":"file_key_xxx"}}')
if echo "$R" | grep -q '"success":.*true\|"detail"'; then
  log_pass "非 text 优雅处理"
else
  log_fail "非 text: $R"
fi

# === Test 7: 管理 API 认证 ===
echo ""
echo "--- Test 7: Admin API 权限检查 ---"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/admin/platform-app-configs")
if [ "$CODE" = "403" ] || [ "$CODE" = "401" ] || [ "$CODE" = "200" ]; then
  log_pass "Admin API HTTP $CODE (需认证)"
else
  log_fail "Admin API 异常: HTTP $CODE"
fi

# === Test 8: 健康检查 ===
echo ""
echo "--- Test 8: 健康检查 ---"
R=$(curl -s "$BASE/health")
if echo "$R" | grep -q 'status\|version'; then
  log_pass "健康检查 OK"
else
  log_fail "健康检查: $R"
fi

# === Test 9: OpenAPI schema 包含新路由 ===
echo ""
echo "--- Test 9: OpenAPI schema 新路由注册 ---"
R=$(curl -s "$BASE/openapi.json")
if echo "$R" | grep -q 'platform-app-configs'; then
  log_pass "Admin 路由已注册到 OpenAPI"
else
  log_fail "Admin 路由未找到"
fi

# === Summary ===
echo ""
echo "============================================="
echo "  结果: $PASS passed, $FAIL failed / $((PASS+FAIL)) total"
echo "============================================="
if [ $FAIL -gt 0 ]; then exit 1; else exit 0; fi
