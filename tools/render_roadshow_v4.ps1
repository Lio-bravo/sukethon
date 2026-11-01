$ErrorActionPreference = 'Stop'
$root = 'E:\Project\sukethon\deliverables\20261101_roadshow_v4_fullfront'
$ppt = Get-ChildItem -LiteralPath $root -Filter '*.pptx' | Select-Object -First 1
if (!$ppt) { throw 'No presentation' }
$preview = Join-Path $root 'preview'
New-Item -ItemType Directory -Force -Path $preview | Out-Null
$app = New-Object -ComObject PowerPoint.Application
$deck = $null
try {
    $deck = $app.Presentations.Open($ppt.FullName, $true, $false, $false)
    if ($deck.Slides.Count -ne 5) { throw 'Unexpected slide count' }
    for ($i=1; $i -le 5; $i++) {
        $slide=$deck.Slides.Item($i)
        $slide.Export((Join-Path $preview ('slide_{0:D2}.png' -f $i)), 'PNG', 1600, 900)
    }
    try { $deck.SaveAs((Join-Path $root 'roadshow_v4.pdf'),32) } catch { Write-Warning ('PDF optional export: '+$_.Exception.Message) }
    Write-Output ('Rendered '+$deck.Slides.Count+' slides with PowerPoint '+$app.Version)
} finally {
    if ($deck) { $deck.Close(); [Runtime.InteropServices.Marshal]::ReleaseComObject($deck) | Out-Null }
    [Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
}
