#!/usr/bin/env python3
"""调试脚本：检查配置和监控状态"""
import sys
import os

# 添加项目根目录到路径
backend_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, project_root)

# 使用绝对导入
from backend.database import get_user_config, get_wecom_config, list_users
from backend.monitor_service import MonitorRegistry

def main():
    print("=== 用户列表 ===")
    users = list_users()
    for user in users:
        user_id = user["id"]
        print(f"\n用户 ID: {user_id}, 邮箱: {user.get('email', 'N/A')}")
        
        print("\n--- 监控配置 ---")
        config = get_user_config(user_id)
        print(f"Telegram Chat ID: {config.get('telegram_chat_id')}")
        print(f"钱包地址: {config.get('wallet_addresses', [])}")
        print(f"语言: {config.get('language', 'zh')}")
        
        print("\n--- 企业微信配置 ---")
        wecom = get_wecom_config(user_id)
        print(f"启用: {wecom.get('enabled', False)}")
        print(f"Webhook URL: {wecom.get('webhook_url', 'N/A')}")
        print(f"手机号: {wecom.get('mentions', [])}")
        
        print("\n--- 监控状态 ---")
        registry = MonitorRegistry()
        monitor = registry.get_monitor(user_id)
        if monitor:
            print(f"监控线程运行中: {monitor._thread and monitor._thread.is_alive() if monitor._thread else False}")
            print(f"配置:")
            print(f"  - Telegram Chat ID: {monitor.config.telegram_chat_id}")
            print(f"  - 钱包地址: {monitor.config.wallet_addresses}")
            print(f"  - 企业微信启用: {monitor.config.wecom_enabled}")
            print(f"  - 企业微信 Webhook: {monitor.config.wecom_webhook_url}")
            if monitor._module:
                print(f"模块配置:")
                print(f"  - TELEGRAM_ENABLED: {getattr(monitor._module, 'TELEGRAM_ENABLED', 'N/A')}")
                print(f"  - TELEGRAM_CHAT_ID: {getattr(monitor._module, 'TELEGRAM_CHAT_ID', 'N/A')}")
                print(f"  - WECOM_ENABLED: {getattr(monitor._module, 'WECOM_ENABLED', 'N/A')}")
                print(f"  - WECOM_WEBHOOK_URL: {getattr(monitor._module, 'WECOM_WEBHOOK_URL', 'N/A')}")
                print(f"  - CONFIGURED_ADDRESSES: {getattr(monitor._module, 'CONFIGURED_ADDRESSES', 'N/A')}")
        else:
            print("监控未初始化")

if __name__ == "__main__":
    main()

