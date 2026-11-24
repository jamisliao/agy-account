# agy-account

[English](README.md) | [繁體中文](README.zh-TW.md)

Multi-account credential manager and millisecond-level profile switcher for Google Antigravity CLI (`agy`) on macOS.

---

## Why agy-account?

The official Google Antigravity CLI (`agy`) stores its user OAuth credentials in the system keychain on macOS (`Service='gemini'`, `Account='antigravity'`).

When working across multiple accounts (e.g., work, personal, or dedicated quota accounts) or running automated batch agents, switching accounts normally requires re-opening a browser for OAuth consent each time.

`agy-account` interacts directly with the macOS Keychain, caching profiles locally and swapping active keychain credentials instantly in milliseconds without browser prompts.

---

## Key Features

1. **Millisecond Keychain Switching**: Swaps active credentials in the macOS Keychain directly. Changes take effect immediately across terminals and third-party tools (such as Paseo IDE).
2. **Cross-Account Protection**: Compares token identity emails before syncing to prevent accidental profile overwrites.
3. **Automated Rotation**: Offers one-command account rotation, ideal for handling rate limits (HTTP 429) during batch operations.
4. **Full Lifecycle Management**: Supports `save`, `switch`, `rotate`, `list`, `current`, `rename`, `delete`, and `test`.
5. **Python Module & CLI**: Functions as a standalone command-line tool or as an importable Python library with context manager support.

---

## Installation

### Method 1: Install script (recommended)

Create a global symlink in `~/.local/bin`:

```bash
cd ~/opensource/agy-account
./install.sh
```

Ensure `~/.local/bin` is included in your `$PATH`.

### Method 2: Editable pip install

```bash
cd ~/opensource/agy-account
pip install -e .
```

---

## Command Reference

### 1. View Status and Profiles

```bash
# Display the currently active profile
agy-account current

# List all saved profiles and their corresponding Google emails
agy-account list
```

### 2. Switch Accounts

```bash
# Switch to a target profile
agy-account switch <alias>

# Automatically rotate to the next saved profile
agy-account rotate
```

### 3. Add a New Google Account

To authenticate and register a new Google account:

```bash
# Step 1: Temporarily clear keychain credentials to trigger the official login flow
security delete-generic-password -s gemini -a antigravity 2>/dev/null
agy -p "ping"

# Step 2: Complete the Google OAuth flow in your browser

# Step 3: Save the newly authenticated session under an alias
agy-account save <alias>
```

### 4. Re-authenticate an Expired Account

```bash
# Switch to the target profile
agy-account switch <alias>

# Re-authenticate and overwrite
security delete-generic-password -s gemini -a antigravity 2>/dev/null
agy -p "ping"
agy-account save <alias>
```

### 5. Maintenance

```bash
# Rename a profile alias
agy-account rename <old-alias> <new-alias>

# Delete a saved profile
agy-account delete <alias>

# Test API connectivity for the currently active profile
agy-account test
```

---

## Python Integration

You can import `AccountManager` directly in automation scripts:

```python
from agy_account import AccountManager

mgr = AccountManager()

# Get the current profile name
print("Active profile:", mgr.get_current_profile())

# Temporarily switch accounts within a block, restoring the previous account on exit
with mgr.temporary_context(target_alias="tool", restore_alias="work"):
    # Runs using the 'tool' account credentials
    pass
# Automatically reverts to 'work'
```

---

## Storage & Architecture

- **Active System Token**: Stored in the native macOS Keychain (`Service='gemini'`, `Account='antigravity'`).
- **Profile Store**: Cached tokens reside in `~/.gemini/antigravity-cli/profiles/` (with strict `0700` directory and `0600` file permissions).
- **Custom Location**: The base directory can be overridden using the `ANTIGRAVITY_CLI_HOME` environment variable.

---

## License

MIT License
