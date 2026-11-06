param([string]$OutputDirectory = 'dist')
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$distRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot $OutputDirectory))
if (-not $distRoot.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw '打包目录必须位于当前仓库内。'
}
Push-Location $repoRoot
try {
    $version = (& python -c "import sys;sys.path.insert(0,'src');import psd_to_spine;print(psd_to_spine.VERSION)").Trim()
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^\d+\.\d+\.\d+$') { throw '读取版本失败。' }
    $packageName = "PSD-to-Spine-v$version-windows-x64"
    $package = Join-Path $distRoot $packageName
    $vendorDirectory = Join-Path $repoRoot 'vendor/photoshop-to-spine'
    python -m PyInstaller --noconfirm --clean --onefile --windowed `
        --name 'PSD一键转Spine' --distpath $package --workpath '.work/pyinstaller' --specpath '.work' `
        --collect-all customtkinter --collect-all tkinterdnd2 `
        --exclude-module numpy `
        --recursive-copy-metadata customtkinter --copy-metadata tkinterdnd2 `
        --add-data "$vendorDirectory;vendor/photoshop-to-spine" 'src/psd_to_spine_gui.py'
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 打包失败。' }
    Copy-Item -LiteralPath 'docs/usage.md' -Destination (Join-Path $package '使用说明.md')
    Copy-Item -LiteralPath 'LICENSE','THIRD_PARTY_NOTICES.md' -Destination $package
    $licenses = Join-Path $package 'licenses'
    New-Item -ItemType Directory -Force -Path $licenses | Out-Null
    Copy-Item -LiteralPath 'vendor/photoshop-to-spine/LICENSE' -Destination (Join-Path $licenses 'PhotoshopToSpine-LICENSE.txt')
    python scripts/collect_licenses.py $licenses
    if ($LASTEXITCODE -ne 0) { throw '依赖许可证收集失败。' }
    $selfCheck = Join-Path $repoRoot '.work/frozen-self-check.json'
    if (Test-Path -LiteralPath $selfCheck) { Remove-Item -LiteralPath $selfCheck }
    $program = Join-Path $package 'PSD一键转Spine.exe'
    $process = Start-Process -FilePath $program -ArgumentList @('--self-check', ('"' + $selfCheck + '"')) -PassThru -WindowStyle Hidden
    if (-not $process.WaitForExit(60000)) { throw '便携版初始化检查超时。' }
    if ($process.ExitCode -ne 0) { throw '便携版初始化检查失败。' }
    $result = Get-Content -LiteralPath $selfCheck -Raw -Encoding utf8 | ConvertFrom-Json
    if (-not $result.ok -or $result.version -ne $version) { throw '便携版资源验证失败。' }
    Compress-Archive -LiteralPath $package -DestinationPath (Join-Path $distRoot "$packageName.zip") -Force
    Write-Output "已生成 $packageName.zip，并通过便携版初始化检查。"
} finally { Pop-Location }
