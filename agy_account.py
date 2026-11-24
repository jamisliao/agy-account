#!/usr/bin/env python3
"""
agy CLI 帳號輪替與憑證管理工具 (macOS Keychain 原生支援版)

原理:
在 macOS 上，Google 官方 Antigravity CLI (agy) 透過系統鑰匙圈
(macOS Keychain: Service='gemini', Account='antigravity')
來儲存與讀取使用者的登入 OAuth Token。

本工具直接與 macOS Keychain 互動：
1. 支援保存多個 Google 帳號憑證至 profiles/ 目錄。
2. 切換帳號時直接更新 Keychain，達成真正「無人介入、毫秒切換、免開瀏覽器」。
3. 自動解析 Token 中的 Google Email，一目瞭然目前是哪一個真實帳號。
4. 支援 Python API 呼叫（上下文管理器、自動輪替重試）以及獨立 CLI 命令列操作。
"""

import os
import sys
import json
import base64
import argparse
import subprocess
from contextlib import contextmanager
from typing import List, Optional, Tuple, Generator

BASE_DIR = os.getenv("ANTIGRAVITY_CLI_HOME", os.path.expanduser("~/.gemini/antigravity-cli"))
PROFILES_DIR = os.path.join(BASE_DIR, "profiles")
ACTIVE_TOKEN_FILE = os.path.join(BASE_DIR, "antigravity-oauth-token")
CURRENT_PROFILE_FILE = os.path.join(PROFILES_DIR, "current_profile.txt")

KEYCHAIN_SERVICE = "gemini"
KEYCHAIN_ACCOUNT = "antigravity"


class AccountManager:
    def __init__(self, profiles_dir: str = PROFILES_DIR):
        self.profiles_dir = profiles_dir
        self.current_profile_file = os.path.join(self.profiles_dir, "current_profile.txt")
        self._ensure_dirs()

    def _ensure_dirs(self):
        if not os.path.exists(self.profiles_dir):
            os.makedirs(self.profiles_dir, mode=0o700, exist_ok=True)
        else:
            try:
                os.chmod(self.profiles_dir, 0o700)
            except OSError:
                pass

    @staticmethod
    def get_keychain_token_raw() -> Optional[str]:
        """從 macOS Keychain 讀取原始憑證字串 (go-keyring 格式)"""
        cmd = [
            "security", "find-generic-password",
            "-s", KEYCHAIN_SERVICE,
            "-a", KEYCHAIN_ACCOUNT,
            "-w"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            return res.stdout.strip()
        return None

    @staticmethod
    def set_keychain_token_raw(val: str) -> bool:
        """寫入原始憑證字串至 macOS Keychain"""
        if not val.startswith("go-keyring-base64:"):
            val = "go-keyring-base64:" + base64.b64encode(val.encode("utf-8")).decode("ascii")

        cmd = [
            "security", "add-generic-password",
            "-U",
            "-s", KEYCHAIN_SERVICE,
            "-a", KEYCHAIN_ACCOUNT,
            "-w", val
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return res.returncode == 0

    @staticmethod
    def parse_token_email(raw_val: str) -> Optional[str]:
        """解析憑證中的 Google Email"""
        try:
            if raw_val.startswith("go-keyring-base64:"):
                raw_bytes = base64.b64decode(raw_val[len("go-keyring-base64:"):])
            else:
                raw_bytes = raw_val.encode("utf-8")
            obj = json.loads(raw_bytes)
            return obj.get("id_token_email") or obj.get("email")
        except Exception:
            return None

    def get_current_profile(self) -> Optional[str]:
        if os.path.exists(self.current_profile_file):
            try:
                with open(self.current_profile_file, "r", encoding="utf-8") as f:
                    curr = f.read().strip()
                    if curr:
                        return curr
            except Exception:
                pass
        return None

    def list_accounts(self) -> List[Tuple[str, Optional[str]]]:
        """返回 [(alias, email), ...]"""
        if not os.path.exists(self.profiles_dir):
            return []
        results = []
        for f in sorted(os.listdir(self.profiles_dir)):
            if f.startswith("token_") and not f.endswith(".tmp"):
                alias = f[6:]
                filepath = os.path.join(self.profiles_dir, f)
                try:
                    with open(filepath, "r", encoding="utf-8") as fp:
                        content = fp.read().strip()
                        email = self.parse_token_email(content)
                except Exception:
                    email = None
                results.append((alias, email))
        return results

    def _sync_back_current(self):
        """將當前 Keychain 中最新憑證回寫存入目前 profile (驗證 Email 一致，防止跨帳號覆寫污染)"""
        curr = self.get_current_profile()
        if not curr:
            return
        kc_token = self.get_keychain_token_raw()
        if not kc_token:
            return

        target = os.path.join(self.profiles_dir, f"token_{curr}")
        if os.path.exists(target):
            try:
                with open(target, "r", encoding="utf-8") as f:
                    orig_content = f.read().strip()
                orig_email = self.parse_token_email(orig_content)
                kc_email = self.parse_token_email(kc_token)
                if orig_email and kc_email and orig_email != kc_email:
                    print(f"⚠️ [防護攔截] Keychain 中的 Email ({kc_email}) 與目前帳號 [{curr}] ({orig_email}) 不符，取消回寫以防止憑證污染！", file=sys.stderr)
                    return
            except Exception:
                pass

        try:
            with open(target, "w", encoding="utf-8") as f:
                f.write(kc_token)
            os.chmod(target, 0o600)
        except Exception as e:
            print(f"⚠️ 回寫帳號 [{curr}] 最新 Token 時發生警告: {e}", file=sys.stderr)

    def save_current_account(self, alias: str) -> bool:
        """將目前 macOS Keychain 正在生效的登入憑證保存為指定別名"""
        alias = alias.strip()
        if not alias:
            print("❌ 錯誤: 帳號別名不能為空！", file=sys.stderr)
            return False

        token_str = self.get_keychain_token_raw()

        if not token_str and os.path.exists(ACTIVE_TOKEN_FILE):
            try:
                with open(ACTIVE_TOKEN_FILE, "r", encoding="utf-8") as f:
                    token_str = f.read().strip()
            except Exception:
                token_str = None

        if not token_str:
            print("❌ 錯誤: 無法在 macOS Keychain 或檔案中找到登入憑證，請先執行 `agy` 完成登入！", file=sys.stderr)
            return False

        email = self.parse_token_email(token_str)
        target_file = os.path.join(self.profiles_dir, f"token_{alias}")
        try:
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(token_str)
            os.chmod(target_file, 0o600)

            with open(self.current_profile_file, "w", encoding="utf-8") as f:
                f.write(alias)

            email_str = f" (Email: {email})" if email else ""
            print(f"✅ 成功保存現行帳號憑證為: [{alias}]{email_str}")
            return True
        except Exception as e:
            print(f"❌ 保存失敗: {e}", file=sys.stderr)
            return False

    def switch_to(self, alias: str) -> bool:
        """切換到指定的帳號別名（直接更新 macOS Keychain）"""
        alias = alias.strip()
        target_file = os.path.join(self.profiles_dir, f"token_{alias}")
        if not os.path.exists(target_file):
            print(f"❌ 錯誤: 找不到帳號 [{alias}] 的憑證檔 ({target_file})", file=sys.stderr)
            return False

        # 1. 先回寫當前 Keychain 內容
        self._sync_back_current()

        # 2. 讀取目標帳號憑證
        try:
            with open(target_file, "r", encoding="utf-8") as f:
                target_token_str = f.read().strip()
        except Exception as e:
            print(f"❌ 讀取目標憑證失敗: {e}", file=sys.stderr)
            return False

        # 3. 寫入 macOS Keychain
        if not self.set_keychain_token_raw(target_token_str):
            print("❌ 更新 macOS Keychain 失敗！", file=sys.stderr)
            return False

        # 4. 同步更新實體檔案 (供相容使用)
        try:
            raw_json = target_token_str
            if raw_json.startswith("go-keyring-base64:"):
                raw_json = base64.b64decode(raw_json[len("go-keyring-base64:"): ]).decode("utf-8")
            with open(ACTIVE_TOKEN_FILE, "w", encoding="utf-8") as f:
                f.write(raw_json)
            os.chmod(ACTIVE_TOKEN_FILE, 0o600)
        except Exception:
            pass

        # 5. 更新當前作用中標記
        with open(self.current_profile_file, "w", encoding="utf-8") as f:
            f.write(alias)

        email = self.parse_token_email(target_token_str)
        email_str = f" ({email})" if email else ""
        print(f"🔄 已切換 agy cli 帳號為: [{alias}]{email_str}")
        return True

    @contextmanager
    def temporary_context(self, target_alias: Optional[str] = None, restore_alias: Optional[str] = None) -> Generator[None, None, None]:
        """帳號上下文管理器：在區塊內臨時切換帳號，結束時復原"""
        original = self.get_current_profile()
        target_restore = restore_alias if restore_alias else original

        if target_alias and target_alias != original:
            print(f"🔀 [帳號切換] 暫時切換工作帳號至: [{target_alias}] (原始帳號: [{original}])")
            self.switch_to(target_alias)

        try:
            yield
        finally:
            current_now = self.get_current_profile()
            if target_restore and current_now != target_restore:
                print(f"🔀 [帳號復原] 作業完成，復原帳號認證至: [{target_restore}]")
                self.switch_to(target_restore)
            elif target_restore:
                print(f"ℹ️ [帳號狀態] 目前帳號維持為: [{target_restore}]")

    def rotate(self) -> Optional[str]:
        """自動輪替至下一個可用帳號"""
        accounts = [a[0] for a in self.list_accounts()]
        if not accounts:
            print("❌ 沒有任何已保存的帳號可供輪換！", file=sys.stderr)
            return None

        current = self.get_current_profile()
        if current in accounts:
            idx = accounts.index(current)
            next_idx = (idx + 1) % len(accounts)
        else:
            next_idx = 0

        next_account = accounts[next_idx]
        if self.switch_to(next_account):
            return next_account
        return None

    def rename_account(self, old_alias: str, new_alias: str) -> bool:
        """重新命名帳號別名"""
        old_alias = old_alias.strip()
        new_alias = new_alias.strip()
        old_file = os.path.join(self.profiles_dir, f"token_{old_alias}")
        new_file = os.path.join(self.profiles_dir, f"token_{new_alias}")

        if not os.path.exists(old_file):
            print(f"❌ 錯誤: 找不到舊帳號別名 [{old_alias}]！", file=sys.stderr)
            return False
        if os.path.exists(new_file):
            print(f"❌ 錯誤: 新帳號別名 [{new_alias}] 已經存在！", file=sys.stderr)
            return False

        try:
            os.rename(old_file, new_file)
            if self.get_current_profile() == old_alias:
                with open(self.current_profile_file, "w", encoding="utf-8") as f:
                    f.write(new_alias)
            print(f"✏️ 帳號別名已更名: [{old_alias}] ➔ [{new_alias}]")
            return True
        except Exception as e:
            print(f"❌ 更名失敗: {e}", file=sys.stderr)
            return False

    def delete_account(self, alias: str) -> bool:
        """刪除指定帳號憑證"""
        alias = alias.strip()
        target_file = os.path.join(self.profiles_dir, f"token_{alias}")
        if not os.path.exists(target_file):
            print(f"❌ 帳號 [{alias}] 不存在。", file=sys.stderr)
            return False
        try:
            os.remove(target_file)
            if self.get_current_profile() == alias:
                if os.path.exists(self.current_profile_file):
                    os.remove(self.current_profile_file)
            print(f"🗑️ 已刪除帳號 [{alias}] 的憑證。")
            return True
        except Exception as e:
            print(f"❌ 刪除失敗: {e}", file=sys.stderr)
            return False

    def test_active_account(self, model: str = "gemini-3.8-flash-high") -> bool:
        """測試目前啟用的帳號連線，並驗證 Google 認證郵箱"""
        current = self.get_current_profile() or "現行登入"
        kc_token = self.get_keychain_token_raw()
        email = self.parse_token_email(kc_token) if kc_token else "未知"

        print(f"🧪 正在測試帳號 [{current}] (Google Email: {email}) 於模型 [{model}]...")

        cmd = [
            "agy",
            "-p", "Ping test. Respond only: PONG",
            "--model", model,
            "--dangerously-skip-permissions"
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if proc.returncode == 0:
                print(f"✅ 連線成功！輸出: {proc.stdout.strip()}")
                return True
            else:
                print(f"❌ 呼叫失敗:\n{proc.stderr.strip()}", file=sys.stderr)
                return False
        except Exception as e:
            print(f"❌ 測試發生例外: {e}", file=sys.stderr)
            return False


def main():
    parser = argparse.ArgumentParser(
        prog="agy-account",
        description="Google Antigravity CLI (agy) 多帳號輪替與憑證管理工具 (macOS Keychain 原生支援)"
    )
    subparsers = parser.add_subparsers(dest="command", help="子指令")

    p_save = subparsers.add_parser("save", help="將當前 Keychain 登入狀態存為別名")
    p_save.add_argument("alias", help="帳號別名 (例如: work, personal, tool)")

    subparsers.add_parser("list", help="列出所有已保存帳號與對應 Email")
    subparsers.add_parser("current", help="顯示目前作用中的帳號")

    p_switch = subparsers.add_parser("switch", help="切換到指定帳號")
    p_switch.add_argument("alias", help="目標帳號別名")

    subparsers.add_parser("rotate", help="自動輪替至下一個可用帳號")

    p_rename = subparsers.add_parser("rename", help="修改帳號別名")
    p_rename.add_argument("old_alias", help="舊帳號別名")
    p_rename.add_argument("new_alias", help="新帳號別名")

    p_del = subparsers.add_parser("delete", help="刪除指定帳號憑證")
    p_del.add_argument("alias", help="欲刪除的帳號別名")

    p_test = subparsers.add_parser("test", help="測試目前啟用帳號的 API 連線")
    p_test.add_argument("--model", default="gemini-3.8-flash-high", help="測試使用的模型 (預設: gemini-3.8-flash-high)")

    args = parser.parse_args()
    mgr = AccountManager()

    if args.command == "save":
        mgr.save_current_account(args.alias)
    elif args.command == "list":
        accounts = mgr.list_accounts()
        current = mgr.get_current_profile()
        print("\n📋 agy CLI 已保存帳號清單:")
        if not accounts:
            print("  (尚無保存的帳號)")
        for alias, email in accounts:
            indicator = "👉 [使用中]" if alias == current else "   "
            email_info = f" ({email})" if email else ""
            print(f"  {indicator} {alias}{email_info}")
        print()
    elif args.command == "current":
        current = mgr.get_current_profile()
        kc_token = mgr.get_keychain_token_raw()
        email = mgr.parse_token_email(kc_token) if kc_token else None
        email_str = f" ({email})" if email else ""
        print(f"👉 目前使用中帳號: [{current}]{email_str}")
    elif args.command == "switch":
        mgr.switch_to(args.alias)
    elif args.command == "rotate":
        new_acc = mgr.rotate()
        if new_acc:
            print(f"✨ 輪替完成，目前生效帳號為: [{new_acc}]")
    elif args.command == "delete":
        mgr.delete_account(args.alias)
    elif args.command == "rename":
        mgr.rename_account(args.old_alias, args.new_alias)
    elif args.command == "test":
        mgr.test_active_account(model=args.model)
    else:
        # 預設無參數時顯示當前帳號與清單
        current = mgr.get_current_profile()
        kc_token = mgr.get_keychain_token_raw()
        email = mgr.parse_token_email(kc_token) if kc_token else None
        email_str = f" ({email})" if email else ""
        print(f"👉 目前作用中帳號: [{current}]{email_str}\n")
        parser.print_help()


if __name__ == "__main__":
    main()
