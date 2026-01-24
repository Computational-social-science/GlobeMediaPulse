# scripts/backup_local_db.ps1

$BackupDir = Join-Path $PSScriptRoot "..\backups"
$BackupDir = [System.IO.Path]::GetFullPath($BackupDir)

if (!(Test-Path -Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
    Write-Host "Created backups directory: $BackupDir"
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupFile = "globemediapulse_backup_$Timestamp.sql"
$ContainerPath = "/tmp/$BackupFile"
$LocalPath = Join-Path $BackupDir $BackupFile

Write-Host "Starting backup of local globemediapulse-db..."

# 1. Dump inside container to avoid shell redirection encoding issues
# Using -d globemediapulse to specify database name explicitly
docker exec globemediapulse-db pg_dump -U postgres -d globemediapulse -f $ContainerPath

if ($LASTEXITCODE -eq 0) {
    # 2. Copy file out
    docker cp "globemediapulse-db:$ContainerPath" "$LocalPath"
    
    # 3. Cleanup inside container
    docker exec globemediapulse-db rm $ContainerPath
    
    Write-Host "Backup completed successfully!" -ForegroundColor Green
    Write-Host "File saved to: $LocalPath"
} else {
    Write-Host "Backup FAILED during pg_dump. Is the container running?" -ForegroundColor Red
    exit 1
}
