# Küçük örnek veriyle tüm hat (Windows PowerShell).
$ErrorActionPreference = "Stop"
$env:IDS_DB = "ids_sample"; $env:PYTHONIOENCODING = "utf-8"
$py = ".venv\Scripts\python.exe"
foreach ($a in @(@("ingest","--sample"), @("clean"), @("features"), @("export"), @("train","--experiment","all","--quick"), @("report"))) {
    & $py -m ids @a; if ($LASTEXITCODE -ne 0) { throw "ids $a basarisiz" }
}
