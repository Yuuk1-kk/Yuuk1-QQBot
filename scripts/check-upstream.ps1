[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$composePath = Join-Path $repoRoot 'compose.yml'
$composeText = Get-Content -LiteralPath $composePath -Raw
$headers = @{
    Accept = 'application/vnd.github+json'
    'User-Agent' = 'Yuuk1-QQBot-upstream-check'
}

function Get-RepositoryImage([string]$VariableName) {
    $pattern = '(?m)^\s*image:\s*\$\{' + [regex]::Escape($VariableName) + ':-([^}]+)\}\s*$'
    $match = [regex]::Match($composeText, $pattern)
    if (-not $match.Success) {
        throw "compose.yml 中找不到 $VariableName 的默认镜像引用。"
    }
    return $match.Groups[1].Value.Trim()
}

function Get-ReleaseClass($Release) {
    $tag = [string]$Release.tag_name
    # GitHub metadata has marked AstrBot v4.29.0-beta.1 as prerelease=false.
    # Always inspect the tag itself as well as the metadata flag.
    if ($tag -match '(?i)(?:^|[._-])(?:alpha|beta|rc|preview|dev|nightly)(?:[._-]|\d|$)' -or
        [bool]$Release.prerelease) {
        return 'BETA'
    }
    return 'STABLE'
}

function Get-ImageDigest([string]$ImageRepository, [string]$Tag) {
    $uri = "https://hub.docker.com/v2/repositories/$ImageRepository/tags/$Tag/"
    $result = Invoke-RestMethod -Uri $uri -TimeoutSec 20
    if ([string]$result.digest -notmatch '^sha256:[a-f0-9]{64}$') {
        throw "Docker Hub 未提供 $ImageRepository`:$Tag 的有效 digest。"
    }
    return [string]$result.digest
}

$projects = @(
    @{ Name = 'AstrBot'; Variable = 'ASTRBOT_IMAGE'; ImageRepository = 'soulter/astrbot'; ReleaseRepository = 'AstrBotDevs/AstrBot' },
    @{ Name = 'NapCat'; Variable = 'NAPCAT_IMAGE'; ImageRepository = 'mlikiowa/napcat-docker'; ReleaseRepository = 'NapNeko/NapCatQQ' }
)

$failed = $false
foreach ($project in $projects) {
    try {
        $image = Get-RepositoryImage $project.Variable
        if ($image -notmatch ('^' + [regex]::Escape($project.ImageRepository) + ':(?<tag>v\d+\.\d+\.\d+(?:[-.][A-Za-z0-9.]+)?)@(?<digest>sha256:[a-f0-9]{64})$')) {
            throw "$($project.Name) 镜像不是已锁定的官方版本 tag + digest。"
        }
        $currentTag = $Matches['tag']
        $currentDigest = $Matches['digest']
        Write-Output "CURRENT $($project.Name): $image"

        $releasesUri = "https://api.github.com/repos/$($project.ReleaseRepository)/releases?per_page=100"
        $releases = Invoke-RestMethod -Uri $releasesUri -Headers $headers -TimeoutSec 20
        $candidates = @($releases | Where-Object {
            -not $_.draft -and [string]$_.tag_name -match '^v\d+\.\d+\.\d+(?:[-.][A-Za-z0-9.]+)?$'
        } | Sort-Object -Property published_at -Descending)

        foreach ($releaseClass in @('STABLE', 'BETA')) {
            $release = $candidates | Where-Object { (Get-ReleaseClass $_) -eq $releaseClass } | Select-Object -First 1
            if ($null -eq $release) {
                Write-Output "AVAILABLE $($project.Name) $releaseClass`: none reported"
                continue
            }
            $tag = [string]$release.tag_name
            $digest = Get-ImageDigest $project.ImageRepository $tag
            Write-Output "AVAILABLE $($project.Name) $releaseClass`: $($project.ImageRepository):$tag@$digest"
        }

        $publishedDigest = Get-ImageDigest $project.ImageRepository $currentTag
        if ($publishedDigest -ne $currentDigest) {
            Write-Warning "$($project.Name) 当前 tag 的 Docker Hub digest 已变化；仓库 pin 仍固定原镜像。升级前请人工复核。"
        }
    } catch {
        $failed = $true
        Write-Warning "$($project.Name) 上游检查失败：$($_.Exception.Message)"
    }
}

if ($failed) { exit 1 }
