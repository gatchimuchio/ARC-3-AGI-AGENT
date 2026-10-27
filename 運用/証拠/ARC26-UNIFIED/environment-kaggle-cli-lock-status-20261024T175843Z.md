# ARC3 Kaggle CLI lock and runtime status

The project lock pins Kaggle CLI 2.2.5, kagglesdk 0.1.38, and certifi 2026.10.19. Read-only, version-pinned Kaggle operations through `uvx --from 'kaggle==2.2.5' kaggle ...` are working.

The existing project virtual environment does not match the lock: Kaggle CLI metadata is None, kagglesdk 0.1.37, certifi 2026.10.19, and the console script exists=False. Project sync state: uv sync --locked failed with Access is denied while replacing kaggle-2.2.4.dist-info/licenses.

No ACL or credential changes were made. Use the pinned `uvx` route for Kaggle CLI operations until the project environment can be synchronized safely.

Evidence: `運用/証拠/ARC26-UNIFIED/environment-kaggle-cli-lock-status-20261024T175843Z.json`
