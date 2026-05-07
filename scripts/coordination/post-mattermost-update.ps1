param(
  [Parameter(Mandatory = $true)][ValidateSet("PLAN","ACK","BLOCK","LOCK","UNLOCK","DECISION","CHANGED","REVIEW_READY","ABORT")][string]$Type,
  [Parameter(Mandatory = $true)][string]$Version,
  [Parameter(Mandatory = $true)][string]$ChangeId,
  [string]$Module = "M8",
  [string]$Risk = "low",
  [Parameter(Mandatory = $true)][string]$Message,
  [string]$Seat = "#1",
  [string]$Channel = $env:MATTERMOST_CHANNEL,
  [string]$Team = $env:MATTERMOST_TEAM,
  [string]$ServerUrl = $env:MATTERMOST_URL,
  [string]$Token = $env:MATTERMOST_TOKEN
)

$ErrorActionPreference = "Stop"

if (-not $ServerUrl) { throw "MATTERMOST_URL is required, for example http://8.141.111.33:8065" }
if (-not $Token) { throw "MATTERMOST_TOKEN is required" }
if (-not $Team) { $Team = "carbonrag" }
if (-not $Channel) { $Channel = "carbonrag-control" }

$ServerUrl = $ServerUrl.TrimEnd("/")
$headers = @{ Authorization = "Bearer $Token" }

$teamInfo = Invoke-RestMethod -Method Get -Uri "$ServerUrl/api/v4/teams/name/$Team" -Headers $headers
$channelInfo = Invoke-RestMethod -Method Get -Uri "$ServerUrl/api/v4/teams/$($teamInfo.id)/channels/name/$Channel" -Headers $headers

$prefix = "[$Seat][$Type][$Version][change-id=$ChangeId][module=$Module][risk=$Risk]"
$body = @{
  channel_id = $channelInfo.id
  message = "$prefix`n$Message"
} | ConvertTo-Json -Depth 5

$post = Invoke-RestMethod -Method Post -Uri "$ServerUrl/api/v4/posts" -Headers ($headers + @{ "Content-Type" = "application/json" }) -Body $body
Write-Host "Posted Mattermost update: $($post.id)"

