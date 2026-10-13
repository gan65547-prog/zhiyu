#!/usr/bin/env python
"""v2.1 多租户接入方案 — 端到端验证脚本"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_all():
    errors = []

    # 1. Fernet
    try:
        from cryptography.fernet import Fernet
        k = Fernet.generate_key()
        assert Fernet(k).decrypt(Fernet(k).encrypt(b'test')).decode() == 'test'
        print('PASS: 1_Fernet')
    except Exception as e:
        errors.append(f'FAIL: 1_Fernet: {e}')

    # 2. build_adapter_config
    try:
        from apps.integration.services.platform_app_config import build_adapter_config
        cfg = build_adapter_config('feishu', {
            'app_id': 'cli_x', 'credentials': {'app_secret': 's'},
            'verification_token': 'vt', 'encrypt_key': 'ek'
        })
        assert cfg['app_id'] == 'cli_x'
        assert cfg['app_secret'] == 's'
        assert cfg['verification_token'] == 'vt'
        print('PASS: 2_adapter_config')
    except Exception as e:
        errors.append(f'FAIL: 2_adapter_config: {e}')

    # 3. UserMappingService signatures
    try:
        from apps.integration.services.user_mapping import UserMappingService
        import inspect
        svc = UserMappingService()
        for method_name in ['get_or_create_user', '_query_existing_mapping', '_auto_register_user']:
            sig = inspect.signature(getattr(svc, method_name))
            params = list(sig.parameters.keys())
            if 'app_config_id' not in params:
                errors.append(f'FAIL: 3_{method_name} missing app_config_id')
        if not hasattr(svc, '_get_tenant_by_app_config'):
            errors.append('FAIL: 3_missing _get_tenant_by_app_config')
        else:
            print('PASS: 3_user_mapping_sigs')
    except Exception as e:
        errors.append(f'FAIL: 3_user_mapping: {e}')

    # 4. QueryService signature
    try:
        from apps.integration.services.query_service import QueryService
        import inspect
        sig = inspect.signature(QueryService.handle_query)
        assert 'app_config_id' in sig.parameters
        print('PASS: 4_query_service_sig')
    except Exception as e:
        errors.append(f'FAIL: 4_query_service: {e}')

    # 5. PAC methods
    try:
        from apps.integration.services.platform_app_config import PlatformAppConfigService
        for m in ['get_config_by_app_id', 'resolve_app_id', 'get_default_config',
                   'create_config', 'update_config']:
            if not hasattr(PlatformAppConfigService, m):
                errors.append(f'FAIL: 5_missing_{m}')
        print('PASS: 5_pac_methods')
    except Exception as e:
        errors.append(f'FAIL: 5_pac: {e}')

    # 6. resolve_app_id (no DB, pure logic)
    try:
        from apps.integration.services.platform_app_config import PlatformAppConfigService
        pac = PlatformAppConfigService(db=None)

        class FakeReq:
            def __init__(self, h=None, u='/chat'):
                self.headers = h or {}
                self.url = u

        import asyncio

        async def run_resolves():
            r1 = await pac.resolve_app_id('feishu', FakeReq(h={'X-Lark-App-Id': 'cli_h'}), None)
            assert r1 == 'cli_h', f'L1 fail: {r1}'

            r2 = await pac.resolve_app_id('feishu', FakeReq(u='/chat?app=cli_q'), None)
            assert r2 == 'cli_q', f'L2 fail: {r2}'

            r3 = await pac.resolve_app_id('wecom', FakeReq(), {'AgentID': '42'})
            assert r3 == '42', f'L3 fail: {r3}'

            r4 = await pac.resolve_app_id('feishu', FakeReq(), None)
            assert r4 is None, f'L4 fail: {r4}'

        asyncio.run(run_resolves())
        print('PASS: 6_resolve_app_id_4levels')
    except Exception as e:
        errors.append(f'FAIL: 6_resolve: {e}')

    # 7. default config
    try:
        from apps.integration.services.platform_app_config import PlatformAppConfigService
        import asyncio
        pac = PlatformAppConfigService(db=None)

        async def check_defaults():
            d = await pac.get_default_config('feishu')
            assert d['_is_default'] is True
            assert 'tenant_id' in d
            assert 'credentials' in d
            d2 = await pac.get_default_config('wecom')
            assert d2['_is_default'] is True

        asyncio.run(check_defaults())
        print('PASS: 7_default_configs')
    except Exception as e:
        errors.append(f'FAIL: 7_defaults: {e}')

    # 8. main.py routes
    try:
        import main
        app = main.app
        routes = [r.path for r in app.routes if hasattr(r, 'path')]
        admin_routes = [r for r in routes if 'platform-app-config' in r]
        chat_routes = [r for r in routes if '/integration/chat' in r]
        assert len(admin_routes) >= 4, f'admin routes: {len(admin_routes)}'
        assert len(chat_routes) >= 1, 'no chat route'
        print(f'PASS: 8_routes (admin={len(admin_routes)}, chat={len(chat_routes)})')
    except Exception as e:
        errors.append(f'FAIL: 8_routes: {e}')

    # 9. webhook fix
    try:
        with open('services/webhook/service.py') as f:
            content = f.read()
        assert 'return False' in content and '无签名验证器' in content
        print('PASS: 9_webhook_fix')
    except Exception as e:
        errors.append(f'FAIL: 9_webhook: {e}')

    # 10. chat.py has PlatformAppConfigService import
    try:
        with open('apps/integration/routers/chat.py') as f:
            content = f.read()
        assert 'PlatformAppConfigService' in content
        assert 'build_adapter_config' in content
        assert 'resolve_app_id' in content
        assert 'ValueError as ve' in content
        print('PASS: 10_chat_changes')
    except Exception as e:
        errors.append(f'FAIL: 10_chat: {e}')

    # Summary
    print(f'\n{"="*40}')
    if errors:
        for err in errors:
            print(err)
        print(f'\nFAILED: {len(errors)} error(s)')
        return 1
    else:
        print(f'ALL 10 TESTS PASSED ✅')
        return 0


if __name__ == '__main__':
    sys.exit(test_all())
