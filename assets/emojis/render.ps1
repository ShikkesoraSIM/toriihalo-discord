Add-Type -AssemblyName System.Drawing
$ErrorActionPreference = 'Stop'
$out = Join-Path $PSScriptRoot 'png'
New-Item -ItemType Directory -Path $out -Force | Out-Null

# Letras dibujadas desde cero, sin fuentes ni assets externos.
$glyphs = @{
    a = @(@(18, 88, 48, 12, 78, 88), @(30, 60, 66, 60))
    b = @(@(22, 88, 22, 12, 58, 12, 74, 25, 74, 38, 59, 49, 22, 49), @(59, 49, 77, 61, 77, 75, 62, 88, 22, 88))
    c = ,@(76, 22, 61, 12, 33, 12, 18, 28, 18, 72, 33, 88, 61, 88, 76, 77)
    d = ,@(22, 88, 22, 12, 53, 12, 77, 34, 77, 66, 53, 88, 22, 88)
    f = @(@(24, 88, 24, 12, 77, 12), @(24, 47, 66, 47))
    s = ,@(77, 20, 63, 12, 32, 12, 18, 26, 18, 38, 32, 50, 62, 50, 77, 63, 77, 75, 63, 88, 31, 88, 18, 80)
    miss = @(@(23, 25, 73, 75), @(73, 25, 23, 75))
}
$colors = @{ a='#5EE0B4'; b='#71BFFF'; c='#C8A4FF'; d='#FFBD73'; f='#FF657D'; s='#FFE27B'; sh='#DDEBFF'; x='#FFE27B'; xh='#DDEBFF'; miss='#FF657D' }

function Stroke($g, $coords, $color, $width, $scaleX=1.0, $shiftX=0.0) {
    $points = [System.Drawing.PointF[]]::new($coords.Count / 2)
    for ($i = 0; $i -lt $points.Count; $i++) {
        $points[$i] = [System.Drawing.PointF]::new(16 + $coords[$i * 2] * $scaleX + $shiftX, 14 + $coords[$i * 2 + 1])
    }
    $pen = [System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml($color), $width)
    $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
    $g.DrawLines($pen, $points)
    $pen.Dispose()
}

foreach ($grade in @('a','b','c','d','f','s','sh','x','xh','miss')) {
    $bitmap = [System.Drawing.Bitmap]::new(512, 512)
    $g = [System.Drawing.Graphics]::FromImage($bitmap)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.ScaleTransform(4, 4)
    $letter = if ($grade -in @('sh','x','xh')) { 's' } else { $grade }
    $paths = $glyphs[$letter]
    $copies = if ($grade -in @('x','xh')) { 2 } else { 1 }
    for ($copy = 0; $copy -lt $copies; $copy++) {
        $sx = if ($copies -eq 2) { 0.56 } else { 1.0 }
        $dx = if ($copies -eq 2) { $copy * 47 - 3 } else { 0.0 }
        foreach ($path in $paths) { Stroke $g $path '#17202D' 17 $sx $dx }
        foreach ($path in $paths) { Stroke $g $path $colors[$grade] 11 $sx $dx }
    }
    if ($grade -in @('sh','xh')) {
        Stroke $g @(85, 3, 85, 17) '#F4B9E4' 3
        Stroke $g @(78, 10, 92, 10) '#F4B9E4' 3
    }
    $g.Dispose()
    $final = [System.Drawing.Bitmap]::new(128, 128)
    $resize = [System.Drawing.Graphics]::FromImage($final)
    $resize.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $resize.DrawImage($bitmap, 0, 0, 128, 128)
    $name = if ($grade -eq 'miss') { 'torii_miss' } else { "torii_grade_$grade" }
    $final.Save((Join-Path $out "$name.png"), [System.Drawing.Imaging.ImageFormat]::Png)
    $resize.Dispose()
    $final.Dispose()
    $bitmap.Dispose()
}
Write-Output "Rendered 10 original icons to $out"
