#!/usr/bin/env python3
"""
公共知识库模板复制功能测试脚本

测试流程：
1. 检查环境连通性
2. 检查系统租户和模板工作空间
3. 创建新租户
4. 验证默认工作空间和公共知识库创建
5. 等待文档复制任务完成
6. 验证文档复制结果

目标服务器由 GANFY_API_BASE_URL 环境变量指定。
"""

import requests
import json
import time
import sys
import os
from typing import Optional, Dict, Any

BASE_URL = os.environ.get("GANFY_API_BASE_URL", "http://127.0.0.1:8000")
API_PREFIX = "/api/v1"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")

def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

def print_info(text: str):
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")

def pretty_json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)

class TemplateCopyTester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.token: Optional[str] = None
        self.admin_email = os.environ.get("GANFY_TEST_ADMIN_EMAIL", "")
        self.admin_password = os.environ.get("GANFY_TEST_ADMIN_PASSWORD", "")
        if not self.admin_email or not self.admin_password:
            raise RuntimeError("Set GANFY_TEST_ADMIN_EMAIL and GANFY_TEST_ADMIN_PASSWORD before running this script.")

    def _get_headers(self) -> Dict[str, str]:
        if not self.token:
            raise ValueError("Not authenticated")
        return {"Authorization": f"Bearer {self.token}"}

    def check_server_health(self) -> bool:
        """检查服务器健康状态"""
        print_header("1. 检查服务器健康状态")
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                print_success(f"服务器正常: {response.status_code}")
                return True
            else:
                print_error(f"服务器响应异常: {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            print_error(f"无法连接到服务器 {self.base_url}")
            return False
        except Exception as e:
            print_error(f"检查失败: {e}")
            return False

    def login(self) -> bool:
        """登录获取token"""
        print_header("2. 管理员登录")
        try:
            response = requests.post(
                f"{self.base_url}{API_PREFIX}/auth/login",
                json={
                    "email": self.admin_email,
                    "password": self.admin_password
                },
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if "data" in data and "access_token" in data["data"]:
                    self.token = data["data"]["access_token"]
                    print_success("登录成功")
                    return True
            print_error(f"登录失败: {response.status_code} - {response.text}")
            return False
        except Exception as e:
            print_error(f"登录异常: {e}")
            return False

    def check_system_tenant(self) -> Optional[Dict[str, Any]]:
        """检查系统租户和模板工作空间"""
        print_header("3. 检查系统租户和模板工作空间")
        try:
            response = requests.get(
                f"{self.base_url}{API_PREFIX}/tenants/",
                headers=self._get_headers(),
                timeout=10
            )
            if response.status_code == 200:
                tenants = response.json().get("data", [])
                system_tenant = None
                for tenant in tenants:
                    if tenant.get("name") == "__system__":
                        system_tenant = tenant
                        break

                if system_tenant:
                    print_success(f"系统租户存在: {system_tenant.get('id')}")
                    print_info(f"  名称: {system_tenant.get('name')}")
                    print_info(f"  状态: {system_tenant.get('status')}")
                    return system_tenant
                else:
                    print_warning("系统租户不存在（模板功能可能未启用）")
                    return None
            else:
                print_error(f"获取租户列表失败: {response.status_code}")
                return None
        except Exception as e:
            print_error(f"检查系统租户异常: {e}")
            return None

    def check_template_workspace(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """检查模板工作空间"""
        print_header("4. 检查系统模板工作空间")
        try:
            response = requests.get(
                f"{self.base_url}{API_PREFIX}/workspaces/",
                headers=self._get_headers(),
                params={"tenant_id": tenant_id},
                timeout=10
            )
            if response.status_code == 200:
                workspaces = response.json().get("data", {}).get("items", [])
                template_ws = None
                for ws in workspaces:
                    if ws.get("name") == "__system_template__":
                        template_ws = ws
                        break

                if template_ws:
                    print_success(f"模板工作空间存在: {template_ws.get('id')}")
                    print_info(f"  名称: {template_ws.get('name')}")
                    print_info(f"  是否默认: {template_ws.get('is_default')}")
                    return template_ws
                else:
                    print_warning("模板工作空间不存在")
                    return None
            else:
                print_error(f"获取工作空间列表失败: {response.status_code}")
                return None
        except Exception as e:
            print_error(f"检查模板工作空间异常: {e}")
            return None

    def check_template_documents(self, workspace_id: str) -> int:
        """检查模板工作空间中的文档数量"""
        try:
            response = requests.get(
                f"{self.base_url}{API_PREFIX}/workspaces/{workspace_id}/datasets",
                headers=self._get_headers(),
                timeout=10
            )
            if response.status_code == 200:
                datasets = response.json().get("data", [])
                total_docs = 0
                for ds in datasets:
                    docs_response = requests.get(
                        f"{self.base_url}{API_PREFIX}/datasets/{ds.get('id')}/documents",
                        headers=self._get_headers(),
                        timeout=10
                    )
                    if docs_response.status_code == 200:
                        docs = docs_response.json().get("data", {}).get("items", [])
                        total_docs += len(docs)
                return total_docs
            return 0
        except Exception as e:
            print_warning(f"检查模板文档失败: {e}")
            return 0

    def create_test_tenant(self) -> Optional[Dict[str, Any]]:
        """创建测试租户"""
        print_header("5. 创建测试租户")
        test_tenant_name = f"测试租户_{int(time.time())}"
        test_email = f"test_{int(time.time())}@example.com"

        try:
            response = requests.post(
                f"{self.base_url}{API_PREFIX}/tenants/",
                headers=self._get_headers(),
                json={
                    "name": test_tenant_name,
                    "contact_email": test_email,
                    "plan": "free",
                    "admin_username": "testadmin",
                    "admin_email": test_email,
                    "admin_password": self.admin_password
                },
                timeout=30
            )
            if response.status_code == 201:
                data = response.json()
                tenant = data.get("data", {})
                print_success(f"租户创建成功: {tenant.get('id')}")
                print_info(f"  名称: {tenant.get('name')}")
                print_info(f"  邮箱: {tenant.get('contact_email')}")
                return tenant
            else:
                print_error(f"创建租户失败: {response.status_code}")
                print_error(f"响应: {response.text}")
                return None
        except Exception as e:
            print_error(f"创建租户异常: {e}")
            return None

    def check_tenant_workspace_and_dataset(self, tenant_id: str) -> tuple:
        """检查租户的默认工作空间和公共知识库"""
        print_header("6. 检查租户默认工作空间和公共知识库")

        try:
            response = requests.get(
                f"{self.base_url}{API_PREFIX}/tenants/{tenant_id}",
                headers=self._get_headers(),
                timeout=10
            )
            if response.status_code == 200:
                tenant = response.json().get("data", {})
                print_info(f"租户状态: {tenant.get('status')}")
                print_info(f"租户计划: {tenant.get('plan')}")

            workspaces_response = requests.get(
                f"{self.base_url}{API_PREFIX}/workspaces/",
                headers=self._get_headers(),
                params={"tenant_id": tenant_id},
                timeout=10
            )

            default_workspace = None
            public_dataset = None

            if workspaces_response.status_code == 200:
                workspaces = workspaces_response.json().get("data", {}).get("items", [])
                print_info(f"工作空间数量: {len(workspaces)}")

                for ws in workspaces:
                    is_default = ws.get("is_default", False)
                    print_info(f"  - {ws.get('name')} (默认: {is_default}, ID: {ws.get('id')})")
                    if is_default:
                        default_workspace = ws

                        datasets_response = requests.get(
                            f"{self.base_url}{API_PREFIX}/datasets/",
                            headers=self._get_headers(),
                            params={"workspace_id": ws.get('id')},
                            timeout=10
                        )
                        if datasets_response.status_code == 200:
                            datasets = datasets_response.json().get("data", {}).get("items", [])
                            for ds in datasets:
                                if ds.get("is_public"):
                                    public_dataset = ds
                                    print_success(f"    公共知识库: {ds.get('name')} (ID: {ds.get('id')})")

                if default_workspace:
                    print_success(f"默认工作空间存在: {default_workspace.get('name')}")
                else:
                    print_error("未找到默认工作空间")

                if public_dataset:
                    print_success(f"公共知识库存在: {public_dataset.get('name')}")
                else:
                    print_warning("未找到公共知识库（可能文档复制尚未完成）")

                return default_workspace, public_dataset

        except Exception as e:
            print_error(f"检查工作空间和数据集异常: {e}")

        return None, None

    def check_dataset_documents(self, dataset_id: str) -> int:
        """检查数据集中的文档数量"""
        try:
            response = requests.get(
                f"{self.base_url}{API_PREFIX}/datasets/{dataset_id}/documents",
                headers=self._get_headers(),
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                documents = data.get("data", {}).get("items", [])
                return len(documents)
        except Exception as e:
            print_warning(f"检查文档失败: {e}")
        return 0

    def wait_for_document_copy(self, dataset_id: str, timeout: int = 30, interval: int = 3) -> bool:
        """等待文档复制完成"""
        print_header("7. 等待文档复制完成")

        start_time = time.time()
        last_count = 0

        while time.time() - start_time < timeout:
            doc_count = self.check_dataset_documents(dataset_id)
            if doc_count > last_count:
                print_info(f"文档数量变化: {last_count} -> {doc_count}")
                last_count = doc_count

            if doc_count > 0:
                print_success(f"文档复制完成，共 {doc_count} 个文档")
                return True

            time.sleep(interval)

        print_warning(f"等待超时，文档数量: {last_count}")
        return last_count > 0

    def run_full_test(self) -> bool:
        """运行完整测试流程"""
        print_header("公共知识库模板复制功能测试")
        print_info(f"目标服务器: {self.base_url}")

        if not self.check_server_health():
            return False

        if not self.login():
            return False

        system_tenant = self.check_system_tenant()
        template_workspace = None
        template_doc_count = 0

        if system_tenant:
            template_workspace = self.check_template_workspace(system_tenant.get("id"))
            if template_workspace:
                template_doc_count = self.check_template_documents(template_workspace.get("id"))
                if template_doc_count > 0:
                    print_success(f"模板工作空间中有 {template_doc_count} 个文档")
                else:
                    print_warning("模板工作空间中无文档（不影响测试流程）")

        test_tenant = self.create_test_tenant()
        if not test_tenant:
            print_error("租户创建失败，测试终止")
            return False

        time.sleep(2)

        default_ws, public_ds = self.check_tenant_workspace_and_dataset(test_tenant.get("id"))

        if not default_ws:
            print_error("测试失败: 默认工作空间未创建")
            return False

        if not public_ds:
            print_warning("公共知识库尚未创建，等待中...")
            time.sleep(5)
            default_ws, public_ds = self.check_tenant_workspace_and_dataset(test_tenant.get("id"))

        if public_ds:
            self.wait_for_document_copy(public_ds.get("id"), timeout=20)

        print_header("测试结果汇总")

        results = {
            "服务器连通性": True,
            "管理员登录": bool(self.token),
            "系统租户存在": bool(system_tenant),
            "模板工作空间存在": bool(template_workspace),
            "租户创建成功": bool(test_tenant),
            "默认工作空间创建": bool(default_ws),
            "公共知识库创建": bool(public_ds),
        }

        all_passed = all(results.values())

        for key, value in results.items():
            if value:
                print_success(f"{key}: 通过")
            else:
                print_error(f"{key}: 失败")

        print()
        if all_passed:
            print_success("🎉 所有核心功能测试通过！")
        else:
            print_warning("⚠ 部分功能测试未通过，请检查日志")

        if template_doc_count > 0 and public_ds:
            final_doc_count = self.check_dataset_documents(public_ds.get("id"))
            if final_doc_count > 0:
                print_success(f"文档复制验证成功: {final_doc_count}/{template_doc_count} 个文档")
            else:
                print_warning(f"模板有 {template_doc_count} 个文档，但租户公共知识库中未找到文档（Celery任务可能未执行）")

        return all_passed


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
        if not target_url.startswith("http"):
            target_url = f"http://{target_url}:8000"
    else:
        target_url = BASE_URL

    tester = TemplateCopyTester(base_url=target_url)
    success = tester.run_full_test()
    sys.exit(0 if success else 1)