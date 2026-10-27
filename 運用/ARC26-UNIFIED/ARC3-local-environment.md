# ARC3 ローカルKaggle運転環境

2026-10-24のARC3依存lockに合わせた隔離環境を作成した。既定の .venv はOneDrive配下のACLにより同期時の旧package削除が拒否されたため、ACLを変更せず別パスを使う。

- lock: repository pyproject.toml / uv.lock
- sync command: set UV_PROJECT_ENVIRONMENT to C:\Users\ohira\AppData\Local\CodexEnvs\ARC3-UNIFIED-v3.0, then run uv sync --locked --no-install-project
- Python: CPython 3.12.10
- Kaggle CLI: 2.2.5
- kagglesdk: 0.1.38
- verified executable: C:\Users\ohira\AppData\Local\CodexEnvs\ARC3-UNIFIED-v3.0\Scripts\kaggle.exe
- verified use: read-only kernels status query for C2-051 version 18 returned RUNNING.

The repository .venv remains mismatched (kaggle 2.2.4 / kagglesdk 0.1.37) and is not the operation environment. Do not run uv sync against it while the OneDrive ACL remains unchanged. The external environment contains no Kaggle credentials; the CLI reads the existing user-level Kaggle credential store.
## PowerShell usage

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'C:\Users\ohira\AppData\Local\CodexEnvs\ARC3-UNIFIED-v3.0'
uv sync --locked --no-install-project
& "$env:UV_PROJECT_ENVIRONMENT\Scripts\kaggle.exe" kernels status 'tecchannn/arc3-model-guided-c2-025'
```

The lock-synced environment is outside the repository so OneDrive ACLs on the default .venv do not block package reconciliation. Keep using the absolute environment path for Kaggle CLI operations.