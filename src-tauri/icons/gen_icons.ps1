# 生成最小有效 ICO（1x1, 32bpp，黑色不透明）写到 icon.ico；
# 其他占位文件保持 1x1 PNG 字节即可（它们在打包阶段才会用到，dev/check 不读）。

$icoHex = '00000100010001010000010020003000000016000000280000000100000002000000010020000000000000000000000000000000000000000000000000000000000000000000FF00000000'
$icoBytes = New-Object byte[] ($icoHex.Length / 2)
for ($i = 0; $i -lt $icoHex.Length; $i += 2) {
    $icoBytes[$i / 2] = [Convert]::ToByte($icoHex.Substring($i, 2), 16)
}
$dir = 'C:\workspace\report-assistant\src-tauri\icons'
[System.IO.File]::WriteAllBytes((Join-Path $dir 'icon.ico'), $icoBytes)

$pngHex = '89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4890000000D49444154789C6300010000000500010D0A2DB40000000049454E44AE426082'
$pngBytes = New-Object byte[] ($pngHex.Length / 2)
for ($i = 0; $i -lt $pngHex.Length; $i += 2) {
    $pngBytes[$i / 2] = [Convert]::ToByte($pngHex.Substring($i, 2), 16)
}
foreach ($f in @('icon.png','32x32.png','128x128.png','128x128@2x.png','icon.icns')) {
    [System.IO.File]::WriteAllBytes((Join-Path $dir $f), $pngBytes)
}
Get-ChildItem $dir | Format-Table Name, Length
