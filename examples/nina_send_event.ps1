# Send a session event to RTSP Timelapse Capture (POST /events).
#
# Events are shown on the finished timelapse as timed captions (if "Overlay
# session events" is ticked on the Video Export tab) and written to a
# <video-name>.events.csv alongside the rendered video either way.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File nina_send_event.ps1 -Title "Meridian Flip"
#   powershell -ExecutionPolicy Bypass -File nina_send_event.ps1 -Title "Autofocus Complete" -Detail "HFR 2.31 -> 1.62" -Category autofocus
#   powershell -ExecutionPolicy Bypass -File nina_send_event.ps1 -Title "Target: M31" -Category target
#
# Events are only accepted while capture is running. If it isn't, the app
# returns 409 and this script exits 0 with a note - a marker sent too early
# should not abort a NINA sequence. Real problems (bad title/time, app not
# reachable) exit 1 so NINA can detect them.
#
# Edit $Port if you changed it on the Integrations tab.

param(
    [Parameter(Mandatory = $true)][string]$Title,
    [string]$Detail,
    [string]$Category,
    [string]$Time    # optional YYYYMMDD-HHMMSS; omit to timestamp on arrival
)

$Port = 8787
$Base = "http://127.0.0.1:$Port"

$payload = @{ title = $Title }
if ($Detail)   { $payload.detail = $Detail }
if ($Category) { $payload.category = $Category }
if ($Time)     { $payload.time = $Time }

$body = $payload | ConvertTo-Json -Compress

try {
    $response = Invoke-RestMethod -Method Post -Uri "$Base/events" `
        -ContentType 'application/json' -Body $body
    Write-Output "Recorded: $($response.time) $($response.title)"
    exit 0
} catch {
    $status = $null
    if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }

    if ($status -eq 409) {
        Write-Output "Capture is not running - event skipped."
        exit 0
    }

    if ($status) {
        Write-Error "Event rejected (HTTP $status): $($_.Exception.Message)"
    } else {
        Write-Error "Could not reach RTSP Timelapse Capture at $Base. Is it running with the Remote Control API enabled?"
    }
    exit 1
}
