# Windows PowerShell 5.1; uses built-in .NET SerialPort. No Python required.
$ErrorActionPreference = 'Stop'
$port = $null
$file = $null
$notes = $null
try {
    Write-Host 'Jura full capture v4 + overlap check and extended EEPROM capture - close Arduino Serial Monitor.'
    Write-Host ('Available ports: ' + ([System.IO.Ports.SerialPort]::GetPortNames() -join ', '))
    $portName = (Read-Host 'Mega port (for example COM4)').Trim().ToUpperInvariant()
    if ($portName -notmatch '^COM[0-9]+$') { throw 'Enter a port such as COM4.' }
    # Explicit local drive-root folder. Never use redirected Documents/OneDrive.
    $folder = 'C:\JuraCaptures'
    Write-Host ('OUTPUT FOLDER: ' + $folder)
    [System.IO.Directory]::CreateDirectory($folder) | Out-Null
    $stem = 'Jura-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
    $path = Join-Path $folder ($stem + '.jura')
    $file = [System.IO.File]::Open($path, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
    $notes = [System.IO.StreamWriter]::new((Join-Path $folder ($stem + '-notes.txt')), $false)
    $notes.AutoFlush = $true
    $notes.WriteLine('Host start UTC: ' + [DateTime]::UtcNow.ToString('o'))
    $notes.WriteLine('Port: ' + $portName + '; USB=500000; Jura receivers=9600 8N1')
    $port = [System.IO.Ports.SerialPort]::new($portName, 500000, [System.IO.Ports.Parity]::None, 8, [System.IO.Ports.StopBits]::One)
    $port.Handshake = [System.IO.Ports.Handshake]::None
    $port.ReadBufferSize = 65536
    $port.ReadTimeout = 100
    $port.WriteTimeout = 1000
    $port.DtrEnable = $true
    $port.RtsEnable = $false
    $port.Open()
    $buffer = New-Object byte[] 8192
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    $sentStart = $false
    $queryRequested = $false
    $stopping = $false
    $stopAt = 0L
    $nextStatus = 1000L
    $written = 0L
    Write-Host ('Saving to: ' + $path)
    Write-Host 'Wait for the start message before turning the Jura on.'
    Write-Host 'Press B to mark boot, C coffee, M menu, or N a generic event.'
    Write-Host 'After boot: R sends overlap check then RT:0000 through RT:07F0 (130 requests total) through Mega 16 -> 1k -> Jura 3.'
    Write-Host 'T optionally sends TY: instead. ONE request total per capture; nothing automatic.'
    Write-Host 'Press ENTER to stop and save. Leave the USB cable plugged in until saved.'
    while ($true) {
        try {
            $n = $port.Read($buffer, 0, $buffer.Length)
            if ($n -gt 0) { $file.Write($buffer, 0, $n); $written += $n }
        } catch [System.TimeoutException] { }
        $elapsed = $timer.ElapsedMilliseconds
        if (-not $sentStart -and -not $stopping -and $elapsed -ge 2500) {
            $port.Write('G')
            $sentStart = $true
            $notes.WriteLine('Start requested at host elapsed ms: ' + $elapsed)
            Write-Host 'Capture start requested. Turn on the Jura now; press B to mark it.'
        }
        if (-not $stopping -and [Console]::KeyAvailable) {
            $key = [Console]::ReadKey($true)
            if ($key.Key -eq [ConsoleKey]::Enter) {
                $port.Write('S')
                $stopping = $true
                $stopAt = $elapsed + 2000
                $notes.WriteLine('Stop requested at host elapsed ms: ' + $elapsed)
                Write-Host 'Stopping receivers and saving the remaining buffered data...'
            } elseif (($key.Key -eq [ConsoleKey]::T -or $key.Key -eq [ConsoleKey]::R) -and $sentStart -and -not $queryRequested) {
                $requestKey = if ($key.Key -eq [ConsoleKey]::R) { 'R' } else { 'T' }
                $commandName = if ($requestKey -eq 'R') { 'RT:0000/0001 overlap + RT:0000..RT:07F0 sweep' } else { 'TY:' }
                $port.Write($requestKey)
                $queryRequested = $true
                $notes.WriteLine(('{2} query requested, host elapsed ms {0}, UTC {1}' -f $elapsed, [DateTime]::UtcNow.ToString('o'), $commandName))
                Write-Host ('ONE ' + $commandName + ' query requested. Wait 4 minutes 30 seconds, then ENTER to save.')
            } elseif ('BCMN'.Contains([string]([char]::ToUpperInvariant($key.KeyChar)))) {
                $label = [char]::ToUpperInvariant($key.KeyChar)
                $notes.WriteLine(('Event {0}, host elapsed ms {1}, UTC {2}' -f $label, $elapsed, [DateTime]::UtcNow.ToString('o')))
                Write-Host ('Marked event ' + $label)
            }
        }
        if ($elapsed -ge $nextStatus) {
            $file.Flush()
            Write-Host ('{0:N0} bytes saved; {1:N0} seconds' -f $written, ($elapsed / 1000))
            $nextStatus = $elapsed + 2000
        }
        if ($stopping -and $elapsed -ge $stopAt) { break }
    }
    $notes.WriteLine('Host stop UTC: ' + [DateTime]::UtcNow.ToString('o'))
    $notes.WriteLine('Saved transport bytes: ' + $written)
    Write-Host ('SAVED: ' + $path)
    Write-Host 'Upload the .jura file and matching notes here. The decoder checks completeness.'
    Write-Host 'Saved-byte count includes framing/status messages, even when Jura is silent.'
} catch {
    Write-Host ('CAPTURE ERROR: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'Any bytes already written are retained. An interrupted capture may lack its final footer.'
    if ($port -and $port.IsOpen) { try { $port.Write('S') } catch { } }
} finally {
    if ($file) { $file.Flush(); $file.Dispose() }
    if ($notes) { $notes.Dispose() }
    if ($port) { if ($port.IsOpen) { $port.Close() }; $port.Dispose() }
}
