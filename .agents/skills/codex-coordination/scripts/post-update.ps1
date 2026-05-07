param(
  [Parameter(Mandatory = $true)][string]$Type,
  [Parameter(Mandatory = $true)][string]$Version,
  [Parameter(Mandatory = $true)][string]$ChangeId,
  [string]$Module = "M8",
  [string]$Risk = "low",
  [Parameter(Mandatory = $true)][string]$Message,
  [string]$Seat = "#1"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
$script = Join-Path $root "scripts/coordination/post-mattermost-update.ps1"

& $script -Type $Type -Version $Version -ChangeId $ChangeId -Module $Module -Risk $Risk -Message $Message -Seat $Seat

