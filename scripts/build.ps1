param([string]$OutputDirectory = 'dist', [string]$PythonExecutable = 'python')
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$distRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot $OutputDirectory))
if (-not $distRoot.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw '打包目录必须位于当前仓库内。'
}
Push-Location $repoRoot
try {
    $version = (& $PythonExecutable -c "import sys;sys.path.insert(0,'src');import psd_to_spine;print(psd_to_spine.VERSION)").Trim()
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^\d+\.\d+\.\d+$') { throw '读取版本失败。' }
    $packageName = "PSD-to-Spine-v$version-windows-x64"
    $package = Join-Path $distRoot $packageName
    $vendorDirectory = Join-Path $repoRoot 'vendor/photoshop-to-spine'
    $documentDirectory = Join-Path $repoRoot ('.work/embedded-notices-' + [guid]::NewGuid().ToString('N'))
    & $PythonExecutable scripts/collect_licenses.py --bundle $documentDirectory
    if ($LASTEXITCODE -ne 0) { throw '内置帮助与许可证收集失败。' }
    & $PythonExecutable -m PyInstaller --noconfirm --clean --onefile --windowed `
        --name 'PSD一键转Spine' --distpath $package --workpath '.work/pyinstaller' --specpath '.work' `
        --collect-all customtkinter --collect-all tkinterdnd2 `
        --exclude-module numpy `
        --recursive-copy-metadata customtkinter --copy-metadata tkinterdnd2 `
        --add-data "$vendorDirectory;vendor/photoshop-to-spine" `
        --add-data "$documentDirectory;documents" 'src/psd_to_spine_gui.py'
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 打包失败。' }
    $selfCheck = Join-Path $repoRoot '.work/frozen-self-check.json'
    if (Test-Path -LiteralPath $selfCheck) { Remove-Item -LiteralPath $selfCheck }
    $program = Join-Path $package 'PSD一键转Spine.exe'
    # Test a copy in a genuinely empty directory, outside the package and with
    # that directory as cwd. All help/license lookups must come from the EXE.
    $smokeFolder = Join-Path $repoRoot ('.work/single-file-check-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $smokeFolder | Out-Null
    $smokeProgram = Join-Path $smokeFolder 'PSD一键转Spine.exe'
    Copy-Item -LiteralPath $program -Destination $smokeProgram
    $process = Start-Process -FilePath $smokeProgram -ArgumentList @('--self-check', ('"' + $selfCheck + '"')) `
        -WorkingDirectory $smokeFolder -PassThru -WindowStyle Hidden
    if (-not $process.WaitForExit(60000)) { throw '便携版初始化检查超时。' }
    if ($process.ExitCode -ne 0) { throw '便携版初始化检查失败。' }
    $result = Get-Content -LiteralPath $selfCheck -Raw -Encoding utf8 | ConvertFrom-Json
    if (-not $result.ok -or $result.version -ne $version -or $result.embedded_documents -lt 6 `
            -or $result.license_viewer -ne 'verified') { throw '单文件版资源或许可查看器验证失败。' }
    if (@(Get-ChildItem -LiteralPath $smokeFolder -Force).Count -ne 1) { throw '单文件版在程序旁生成了额外文件。' }
    if (@(Get-ChildItem -LiteralPath $package -Force).Count -ne 1) { throw '发行目录必须只有一个 EXE，请选择新的打包目录。' }
    $standalone = Join-Path $distRoot "$packageName.exe"
    Copy-Item -LiteralPath $program -Destination $standalone
    Write-Output "已生成 $packageName.exe，并通过单文件启动及内置许可完整性检查。"
} finally { Pop-Location }
