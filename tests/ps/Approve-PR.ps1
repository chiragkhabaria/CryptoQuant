param(
    [Parameter(Mandatory=$false)]
    [string]$PRNumber,
    
    [Parameter(Mandatory=$false)]
    [string]$Comment = "LGTM - Changes reviewed and approved"
)

$ErrorActionPreference = "Stop"

if (-not $PRNumber) {
    $PRNumber = gh pr list --limit 1 --json number --jq '.[0].number'
}

Write-Host "Approving PR #$PRNumber..." -ForegroundColor Cyan

gh pr review $PRNumber --approve --body $Comment

Write-Host "`n✅ PR #$PRNumber approved" -ForegroundColor Green
Write-Host "Merging PR..." -ForegroundColor Cyan

gh pr merge $PRNumber --squash --delete-branch

Write-Host "`n✅ PR merged and branch deleted" -ForegroundColor Green
