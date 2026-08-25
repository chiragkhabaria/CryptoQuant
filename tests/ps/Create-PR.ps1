param(
    [Parameter(Mandatory=$false)]
    [string]$Title,
    
    [Parameter(Mandatory=$false)]
    [string]$Body = "Automated PR for recent changes",
    
    [Parameter(Mandatory=$false)]
    [string]$Base = "main",
    
    [Parameter(Mandatory=$false)]
    [string]$Head
)

$ErrorActionPreference = "Stop"

if (-not $Head) {
    $Head = git branch --show-current
}

if (-not $Title) {
    $lastCommit = git log -1 --pretty=%B
    $Title = $lastCommit
}

Write-Host "Creating PR..." -ForegroundColor Cyan
Write-Host "  From: $Head" -ForegroundColor Yellow
Write-Host "  To: $Base" -ForegroundColor Yellow
Write-Host "  Title: $Title" -ForegroundColor Yellow

gh pr create --base $Base --head $Head --title $Title --body $Body

Write-Host "`n✅ PR created successfully" -ForegroundColor Green
