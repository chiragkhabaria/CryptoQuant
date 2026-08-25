param(
    [Parameter(Mandatory=$false)]
    [string]$PRNumber
)

$ErrorActionPreference = "Stop"

if (-not $PRNumber) {
    $PRNumber = gh pr list --limit 1 --json number --jq '.[0].number'
}

Write-Host "`n" -NoNewline
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host (" PR #$PRNumber - Changes Summary " -f $PRNumber) -NoNewline -ForegroundColor Yellow
Write-Host ("=" * 50) -ForegroundColor Cyan

Write-Host "`nFiles Changed:" -ForegroundColor Cyan
gh pr diff $PRNumber --name-only | ForEach-Object {
    Write-Host "  📄 $_" -ForegroundColor White
}

Write-Host "`nDetailed Diff:" -ForegroundColor Cyan
gh pr diff $PRNumber

Write-Host "`n" -NoNewline
Write-Host ("=" * 80) -ForegroundColor Cyan
Write-Host "Review complete. Use Approve-PR.ps1 to approve." -ForegroundColor Yellow
