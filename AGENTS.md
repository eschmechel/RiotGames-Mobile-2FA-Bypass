# AGENTS.md

## Project Overview

**Project Name:** Riot 2FA
**Version:** 2.0.0
**Type:** Desktop Application (Python/PyQt6)
**Platform:** Windows only
**Purpose:** Desktop utility to manage Riot Games TOTP 2FA codes with full encryption at rest,
app-level authentication, and OS secure storage via Windows Credential Manager.

---

## Commands

### Install dependencies
```bash
pip install -r requirements.txt
```

### Run the application
```bash
python main.py
```

### Build executable
```bash
pyinstaller --onefile --windowed --name Riot2FA \
  --hidden-import=keyring.backends.Windows \
  --collect-all keyring \
  main.py
```

### Lint
```bash
flake8 app/ main.py --max-line-length=100
```

---

## Conventions

- **Code style:** PEP 8, max line length 100, type hints required on all functions
- **Imports:** Absolute imports from `app.` root
- **UI:** PyQt6 with Fusion style, custom QSS stylesheet
- **Enums:** Always use full PyQt6 enum syntax e.g. `QLineEdit.EchoMode.Password` (not `QLineEdit.Password`)
- **API:** Direct Riot API calls with JWT handling; validate `iss` and `exp` claims
- **Storage:** Encrypted JSON blob in `%appdata%/Riot2FA/accounts.json` (version 2 format)
- **Config:** `%appdata%/Riot2FA/config.json` stores auth hash, salt, encrypted DEK
- **Logs:** `%appdata%/Riot2FA/logs/audit.log` — rotating, 10 MB x 5 files

---

## Security Requirements

- **Never** log or expose TOTP seeds, passwords, encryption keys, or tokens
- **Never** commit secrets, credentials, or `.env` files
- All TOTP seeds encrypted at rest with AES-256-GCM (DEK/KEK model)
- App-level authentication required before accessing any account data
- Password re-authentication required before "View Seed" or "Copy Seed" actions
- Use `keyring` (Windows Credential Manager) for DEK storage — never plaintext
- Sanitize CR/LF from all user-supplied data before writing to audit log
- Use `QLineEdit.EchoMode.Password` for all password input fields

---

## Cryptographic Standards

| Component         | Standard              | Parameter                        |
| ----------------- | --------------------- | -------------------------------- |
| Data encryption   | AES-256-GCM           | 256-bit key, 96-bit nonce        |
| Key derivation    | PBKDF2-HMAC-SHA256    | 1,200,000 iterations, 16B salt   |
| Password hashing  | Argon2id              | argon2-cffi defaults (RFC 9106)  |
| DEK generation    | AESGCM.generate_key() | bit_length=256                   |
| OS key storage    | Windows Credential Manager | via `keyring` library       |

---

## Important Files

| File                          | Purpose                                              |
| ----------------------------- | ---------------------------------------------------- |
| `main.py`                     | Entry point                                          |
| `app/main.py`                 | App init, auth flow before MainWindow                |
| `app/api/riot_api.py`         | Riot API integration, JWT validation                 |
| `app/core/auth_totp.py`       | TOTP code generation                                 |
| `app/core/storage.py`         | Encrypted account storage (DEK-based)                |
| `app/core/encryption.py`      | AES-256-GCM, PBKDF2, DEK/KEK operations              |
| `app/core/auth.py`            | Argon2id hashing, keyring wrapper, lockout tracker   |
| `app/core/logger.py`          | Structured audit logging                             |
| `app/ui/main_window.py`       | Main UI, lock icon, Reset Password entry             |
| `app/ui/password_dialog.py`   | Setup, Unlock, Reauth, Reset password dialogs        |
| `app/ui/login_browser_dialog.py` | OAuth login flow                                  |
| `app/ui/account_card.py`      | Account card, seed access gated behind reauth        |

---

## Branch & PR Conventions

Each phase is developed on its own branch and merged via PR:

| Branch                         | Phase                   | PR Required |
| ------------------------------ | ----------------------- | ----------- |
| `main`                         | Phase 0 (AGENTS.md)     | No          |
| `phase/1-core-infrastructure`  | Phase 1                 | Yes         |
| `phase/2-storage-layer`        | Phase 2                 | Yes         |
| `phase/3-auth-ui`              | Phase 3                 | Yes         |
| `phase/4-security-hardening`   | Phase 4                 | Yes         |
| `phase/5-cicd`                 | Phase 5                 | Yes         |
| `phase/6-docs`                 | Phase 6                 | Yes         |

Branch off `main` for each phase. Merge to `main` before starting the next phase.

---

## Dependency Versions

| Package        | Version    | Purpose                                  |
| -------------- | ---------- | ---------------------------------------- |
| PyQt6          | latest     | UI framework                             |
| PyQt6-WebEngine| latest     | Embedded browser for OAuth login         |
| requests       | latest     | HTTP client for Riot API                 |
| cryptography   | >=41.0.0   | AES-256-GCM, PBKDF2 key derivation       |
| keyring        | >=24.0.0   | Windows Credential Manager integration   |
| argon2-cffi    | >=25.1.0   | Argon2id password hashing                |
| pyinstaller    | >=6.0.0    | Build tool (replaces Nuitka)             |

> **Note:** Nuitka was removed due to confirmed keyring incompatibility
> (Nuitka issue #3661, November 2025 — `RuntimeError: Requires Windows and pywin32`).

---

## CI/CD

- **CI:** Runs on push to `main` and all PRs — lint + build check
- **Release:** Runs on tag push `v*.*.*` — builds `.exe` and publishes GitHub Release
- Workflow files: `.github/workflows/ci.yml`, `.github/workflows/release.yml`
- Release via `gh` CLI (pre-installed on GitHub runners, no third-party action dependency)

### Tagging a release
```bash
git tag v2.0.0
git push origin v2.0.0
```

---

## Security Notes

- **PyInstaller bytecode:** PyInstaller-packaged executables have extractable Python bytecode.
  Our secrets are encrypted at rest (AES-256-GCM) with keys in Windows Credential Manager,
  so bytecode extraction alone does not expose TOTP seeds.
- **CVE-2025-59042:** PyInstaller < 6.0.0 had a local privilege escalation vulnerability.
  We require `pyinstaller>=6.0.0` which includes the fix.
- **Keyring backend:** We use Windows Credential Manager via `keyring` — not the insecure
  CryptedFileKeyring that had CVE-2012-4571.
