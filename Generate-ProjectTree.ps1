param(
    [string]$RootPath = ".",
    [string]$OutputFile = "project-tree.txt",
    [switch]$IncludeSizes
)

# Directories to exclude
$ExcludeDirs = @(
    ".git",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
    "coverage",
    "target",
    "bin",
    "obj",
    ".terraform",
    ".cache"
)

# File patterns to exclude
$ExcludeFiles = @(
    "*.pyc",
    "*.pyo",
    "*.log",
    "*.tmp",
    "*.tsbuildinfo"
)

$output = New-Object System.Collections.Generic.List[string]

function Get-Tree {
    param(
        [string]$Path,
        [string]$Indent = ""
    )

    $items = Get-ChildItem -LiteralPath $Path -Force |
        Where-Object {

            # Exclude directories
            if ($_.PSIsContainer -and $ExcludeDirs -contains $_.Name) {
                return $false
            }

            # Exclude files
            foreach ($pattern in $ExcludeFiles) {
                if (-not $_.PSIsContainer -and $_.Name -like $pattern) {
                    return $false
                }
            }

            return $true
        } |
        Sort-Object -Property @{Expression="PSIsContainer";Descending=$true}, Name

    for ($i = 0; $i -lt $items.Count; $i++) {

        $item = $items[$i]

        $isLast = ($i -eq ($items.Count - 1))

        if ($isLast) {
            $branch = "\-- "
            $nextIndent = "$Indent    "
        }
        else {
            $branch = "+-- "
            $nextIndent = "$Indent|   "
        }

        if ($item.PSIsContainer) {
            $line = "$Indent$branch$($item.Name)/"
        }
        else {

            if ($IncludeSizes) {
                $sizeKB = [math]::Round($item.Length / 1KB, 2)
                $line = "$Indent$branch$($item.Name) [$sizeKB KB]"
            }
            else {
                $line = "$Indent$branch$($item.Name)"
            }
        }

        $output.Add($line)

        if ($item.PSIsContainer) {
            Get-Tree -Path $item.FullName -Indent $nextIndent
        }
    }
}

$rootItem = Get-Item $RootPath
$output.Add("$($rootItem.Name)/")

Get-Tree -Path $rootItem.FullName

$output | Out-File -Encoding utf8 $OutputFile

Write-Host ""
Write-Host "Project tree exported to: $OutputFile" -ForegroundColor Green
Write-Host ""