# Tam veriyle tüm hat (Windows PowerShell). Disk/RAM gereksinimi için README.
$ErrorActionPreference = "Stop"
$env:IDS_DB = "ids"; $env:PYTHONIOENCODING = "utf-8"
$py = ".venv\Scripts\python.exe"
foreach ($a in @(@("download"), @("make-sample"), @("ingest","--delete-csv"), @("clean"), @("features"), @("export"), @("train","--experiment","all"), @("bench"), @("report"))) {
    & $py -m ids @a; if ($LASTEXITCODE -ne 0) { throw "ids $a basarisiz" }
}
