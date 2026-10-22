param()

$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$repoPath = Split-Path -Parent $PSScriptRoot

Push-Location -LiteralPath $repoPath
try {
    python -c "import sys; assert sys.version_info[:2] == (3, 12), 'Python 3.12が必要です'"
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12を導入してください。' }
    $uvVersion = python -m uv --version 2>$null
    if ($LASTEXITCODE -ne 0 -or $uvVersion -notmatch '^uv 0\.12\.19\b') {
        python -m pip install --user uv==0.12.19
        if ($LASTEXITCODE -ne 0) { throw 'uvの導入に失敗しました。' }
    }
    python -m uv sync --locked
    if ($LASTEXITCODE -ne 0) { throw '依存の復元に失敗しました。' }
    python -m uv run --locked python -m ipykernel install --sys-prefix --name arc3 --display-name 'ARC3 (Python 3.12)'
    if ($LASTEXITCODE -ne 0) { throw 'カーネルの登録に失敗しました。' }
    python -m uv run --locked python 道具/リポジトリ環境監査.py
    if ($LASTEXITCODE -ne 0) { throw 'リポジトリ監査に失敗しました。' }
    python -m uv run --locked python 道具/開発環境確認.py
    if ($LASTEXITCODE -ne 0) { throw '環境確認に失敗しました。接続/開発環境.mdを確認してください。' }
}
finally {
    Pop-Location
}
