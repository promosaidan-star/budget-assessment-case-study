# Open a workbook in its OWN Tableau instance (other Tableau windows are left alone), capture the dashboard area, close it.
# Usage: snap.ps1 <twb> <out.png>
param([string]$Twb, [string]$Out)
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class W32s {
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
}
"@
$p = Start-Process "C:\Program Files\Tableau\Tableau 2026.2\bin\tableau.exe" -ArgumentList "`"$Twb`"" -PassThru
$deadline = (Get-Date).AddSeconds(80)
do { Start-Sleep -Seconds 3; $p.Refresh() } until (($p.MainWindowTitle -match ' - ') -or (Get-Date) -gt $deadline)
if ($p.MainWindowTitle -notmatch ' - ') { "did not load: '$($p.MainWindowTitle)'"; $p | Stop-Process -Force; exit 1 }
$h = $p.MainWindowHandle
[W32s]::ShowWindow($h, 4) | Out-Null
[W32s]::SetWindowPos($h, [IntPtr]1, 0, 0, 1946, 1226, 0x0010) | Out-Null
Start-Sleep -Seconds 12
$r = New-Object W32s+RECT; [W32s]::GetWindowRect($h, [ref]$r) | Out-Null
$bmp = New-Object System.Drawing.Bitmap(($r.R - $r.L), ($r.B - $r.T))
$g = [System.Drawing.Graphics]::FromImage($bmp); $hdc = $g.GetHdc()
[W32s]::PrintWindow($h, $hdc, 2) | Out-Null; $g.ReleaseHdc($hdc); $g.Dispose()
$crop = New-Object System.Drawing.Rectangle(332, 138, 1494, 898)        # dashboard canvas only: no title bar, menus or side panes
$c = $bmp.Clone($crop, $bmp.PixelFormat); $c.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png); $c.Dispose(); $bmp.Dispose()
"captured $Out from '$($p.MainWindowTitle)'"
$p | Stop-Process -Force
