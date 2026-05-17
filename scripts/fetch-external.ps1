param(
  [string]$Root = (Resolve-Path ".").Path
)

$ErrorActionPreference = "Stop"

function Download-And-ExtractZip {
  param(
    [Parameter(Mandatory=$true)][string]$ZipUrl,
    [Parameter(Mandatory=$true)][string]$DestDir,
    [Parameter(Mandatory=$true)][string]$Name
  )

  $tmpDir = Join-Path $env:TEMP "eduaihub_external"
  New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
  $zipPath = Join-Path $tmpDir "$Name.zip"

  Write-Host "Downloading $Name..."
  Invoke-WebRequest -Uri $ZipUrl -OutFile $zipPath

  if (Test-Path $DestDir) {
    Remove-Item -Recurse -Force $DestDir
  }
  New-Item -ItemType Directory -Force -Path $DestDir | Out-Null

  $extractDir = Join-Path $tmpDir "$Name-extract"
  if (Test-Path $extractDir) {
    Remove-Item -Recurse -Force $extractDir
  }
  New-Item -ItemType Directory -Force -Path $extractDir | Out-Null

  Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

  $top = Get-ChildItem -Path $extractDir | Select-Object -First 1
  if ($null -eq $top) {
    throw "Extract failed for $Name"
  }
  Copy-Item -Path (Join-Path $top.FullName "*") -Destination $DestDir -Recurse -Force

  Remove-Item -Force $zipPath
  Remove-Item -Recurse -Force $extractDir
}

$externalDir = Join-Path $Root "external"
$appsDir = Join-Path $Root "apps"

New-Item -ItemType Directory -Force -Path $externalDir | Out-Null
New-Item -ItemType Directory -Force -Path $appsDir | Out-Null

Download-And-ExtractZip `
  -ZipUrl "https://codeload.github.com/ColorlibHQ/AdminLTE/zip/refs/heads/master" `
  -DestDir (Join-Path $externalDir "AdminLTE") `
  -Name "AdminLTE"

Download-And-ExtractZip `
  -ZipUrl "https://codeload.github.com/HKUDS/DeepTutor/zip/refs/heads/main" `
  -DestDir (Join-Path $appsDir "DeepTutor") `
  -Name "DeepTutor"

Write-Host "Done."

