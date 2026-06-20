# PowerShell variant of the Remote Control API calls (alternative to the .bat files).
# Usage:
#   powershell -ExecutionPolicy Bypass -File nina_capture.ps1 start
#   powershell -ExecutionPolicy Bypass -File nina_capture.ps1 stop
#   powershell -ExecutionPolicy Bypass -File nina_capture.ps1 video            # newest session
#   powershell -ExecutionPolicy Bypass -File nina_capture.ps1 video 20250620   # specific night
#
# Edit $Port if you changed it on the Integrations tab.

param(
    [Parameter(Mandatory = $true)][ValidateSet('start', 'stop', 'video', 'status')]
    [string]$Action,
    [string]$Date
)

$Port = 8787
$Base = "http://127.0.0.1:$Port"

switch ($Action) {
    'start'  { Invoke-RestMethod -Method Post -Uri "$Base/capture/start" | ConvertTo-Json }
    'stop'   { Invoke-RestMethod -Method Post -Uri "$Base/capture/stop"  | ConvertTo-Json }
    'status' { Invoke-RestMethod -Method Get  -Uri "$Base/status"        | ConvertTo-Json }
    'video'  {
        if ($Date) {
            $body = @{ date = $Date } | ConvertTo-Json
            Invoke-RestMethod -Method Post -Uri "$Base/video/create" -ContentType 'application/json' -Body $body | ConvertTo-Json
        } else {
            Invoke-RestMethod -Method Post -Uri "$Base/video/create" | ConvertTo-Json
        }
    }
}
