import os
import json
import base64
import tempfile
import unittest
from unittest.mock import patch

from agy_account import AccountManager


class TestAccountManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mgr = AccountManager(profiles_dir=self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_mock_token(self, email="test@example.com"):
        payload = json.dumps({"email": email, "access_token": "mock_token"})
        b64 = base64.b64encode(payload.encode("utf-8")).decode("ascii")
        return f"go-keyring-base64:{b64}"

    def test_parse_token_email(self):
        token_str = self._create_mock_token("developer@example.com")
        email = AccountManager.parse_token_email(token_str)
        self.assertEqual(email, "developer@example.com")

        # Fallback raw json
        raw_json = json.dumps({"id_token_email": "alt@example.com"})
        email_raw = AccountManager.parse_token_email(raw_json)
        self.assertEqual(email_raw, "alt@example.com")

        # Invalid string
        self.assertIsNone(AccountManager.parse_token_email("invalid-data"))

    @patch.object(AccountManager, "get_keychain_token_raw")
    def test_save_and_list_accounts(self, mock_get_token):
        mock_get_token.return_value = self._create_mock_token("acc1@example.com")

        # Save account 1
        res = self.mgr.save_current_account("acc1")
        self.assertTrue(res)
        self.assertEqual(self.mgr.get_current_profile(), "acc1")

        # Save account 2
        mock_get_token.return_value = self._create_mock_token("acc2@example.com")
        self.mgr.save_current_account("acc2")
        self.assertEqual(self.mgr.get_current_profile(), "acc2")

        # List
        accounts = self.mgr.list_accounts()
        self.assertEqual(len(accounts), 2)
        aliases = [a[0] for a in accounts]
        self.assertIn("acc1", aliases)
        self.assertIn("acc2", aliases)

    @patch.object(AccountManager, "set_keychain_token_raw")
    @patch.object(AccountManager, "get_keychain_token_raw")
    def test_switch_and_rotate(self, mock_get_token, mock_set_token):
        mock_set_token.return_value = True
        mock_get_token.return_value = self._create_mock_token("user1@example.com")
        self.mgr.save_current_account("user1")

        mock_get_token.return_value = self._create_mock_token("user2@example.com")
        self.mgr.save_current_account("user2")

        # Switch
        res = self.mgr.switch_to("user1")
        self.assertTrue(res)
        self.assertEqual(self.mgr.get_current_profile(), "user1")

        # Rotate
        next_acc = self.mgr.rotate()
        self.assertEqual(next_acc, "user2")
        self.assertEqual(self.mgr.get_current_profile(), "user2")

    @patch.object(AccountManager, "get_keychain_token_raw")
    def test_rename_and_delete(self, mock_get_token):
        mock_get_token.return_value = self._create_mock_token("temp@example.com")
        self.mgr.save_current_account("temp_name")

        # Rename
        res = self.mgr.rename_account("temp_name", "new_name")
        self.assertTrue(res)
        self.assertEqual(self.mgr.get_current_profile(), "new_name")
        self.assertFalse(os.path.exists(os.path.join(self.mgr.profiles_dir, "token_temp_name")))
        self.assertTrue(os.path.exists(os.path.join(self.mgr.profiles_dir, "token_new_name")))

        # Delete
        del_res = self.mgr.delete_account("new_name")
        self.assertTrue(del_res)
        self.assertEqual(len(self.mgr.list_accounts()), 0)


if __name__ == "__main__":
    unittest.main()
