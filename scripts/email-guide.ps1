<#
.SYNOPSIS
  Open an Outlook draft with the foundryLab learning guide attached.

.DESCRIPTION
  Creates a draft email (NOT sent) in Outlook, addressed to 146099412+samoletovs@users.noreply.github.com,
  with foundryLab/docs/learning-guide.md attached. You review and click Send.

  Falls back gracefully if Outlook is not installed: prints the file path and
  a suggested subject so you can attach manually.

.EXAMPLE
  ./email-guide.ps1
#>

[CmdletBinding()]
param(
  [string]$To = "146099412+samoletovs@users.noreply.github.com",
  [string]$Subject = "[foundryLab] Agent Development Primer for D365 Consultants",
  [string]$GuidePath = "$PSScriptRoot\..\docs\learning-guide.md"
)

$ErrorActionPreference = 'Stop'

$resolved = Resolve-Path $GuidePath -ErrorAction Stop
Write-Host "Guide: $resolved"

$body = @"
Hi Sam,

Below is the agent-development primer we drafted while building the foundryLab
labMemoryAgent. Restructured around two evidence-based learning frameworks:

  - Diataxis (Divio) — separating tutorial / how-to / reference / explanation
  - Worked-example effect (Sweller) — concrete first, generalize after

Every concept follows the same pattern:
  1. In our agent — what we did, with file paths and code
  2. What's actually happening — the underlying concept, generalized
  3. For a customer build — how to adapt for D365 / Microsoft customers

Sections:

  1. The agent we built, at a glance
  2. The mental model (Foundry concepts via D365 analogies)
  3. Walkthrough of every concept (provisioning, ingestion, agent definition,
     calling, evaluation) — the worked example
  4. Foundry vs Copilot Studio vs custom Azure (decision flowchart)
  5. Customer scenarios mapped to platforms (D365 F&O lens)
  6. A first agent project to pitch a customer
  7. Pitfalls (10 things that cost me hours)
  8. Self-check (retrieval-practice questions with hidden answers)
  9. Where to go next (read + build + cert paths)

Reading time ~25 minutes. Best read in two sittings: parts 1-3 first, then
parts 4-9.

The full markdown file is attached.

Cheers
"@

try {
  $outlook = New-Object -ComObject Outlook.Application
} catch {
  Write-Host ""
  Write-Host "Outlook is not available on this machine." -ForegroundColor Yellow
  Write-Host "Manual fallback:" -ForegroundColor Yellow
  Write-Host "  To:      $To"
  Write-Host "  Subject: $Subject"
  Write-Host "  Attach:  $resolved"
  Write-Host ""
  Write-Host "Body:"
  Write-Host $body
  exit 0
}

$mail = $outlook.CreateItem(0)
$mail.To = $To
$mail.Subject = $Subject
$mail.Body = $body
$mail.Attachments.Add($resolved.Path) | Out-Null
$mail.Display()  # opens the draft window — does NOT send

Write-Host ""
Write-Host "Draft opened in Outlook. Review and click Send when ready." -ForegroundColor Green
