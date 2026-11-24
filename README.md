# agy-account

macOS Keychain account manager and rotation utility for Antigravity CLI (`agy`).

## Features

- **Fast Keychain Switching**: Directly swaps OAuth tokens in macOS Keychain (`gemini`/`antigravity`) without reopening a browser.
- **Token Protection**: Validates account emails during profile sync to prevent cross-account overwrites.
- **Account Rotation**: Allows quick command-line rotation and Python context manager rotation across multiple saved accounts.
- **Paseo Ready**: Seamlessly switches the active account for Paseo IDE and related ACP providers.

## Installation

```bash
cd ~/opensource/agy-account
./install.sh
```

Or install with pip:

```bash
pip install -e .
```

## CLI Usage

- `agy-account save <alias>`: Save active Keychain credentials under an alias.
- `agy-account list`: Show all saved profiles with associated emails.
- `agy-account current`: Display the current active profile.
- `agy-account switch <alias>`: Switch Keychain credentials to the target profile.
- `agy-account rotate`: Rotate to the next available saved account.
- `agy-account rename <old> <new>`: Rename an existing profile.
- `agy-account delete <alias>`: Remove a profile.
- `agy-account test`: Verify API connectivity with the current active account.

## Python Integration

```python
from agy_account import AccountManager

mgr = AccountManager()
print("Current profile:", mgr.get_current_profile())

# Temporary switch with auto-restore
with mgr.temporary_context(target_alias="tool", restore_alias="work"):
    # Run tasks with tool account credentials
    pass
```

## License

MIT
