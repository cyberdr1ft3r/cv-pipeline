param(
    [Parameter(Mandatory = $true)]
    [string]$DockerHubUser,

    [string]$Tag = "latest",

    [string]$FrontendApiUrl = "/api/v1",

    [switch]$SkipPush
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

$ApiImage = "${DockerHubUser}/cv-pipeline-api:${Tag}"
$FrontendImage = "${DockerHubUser}/cv-pipeline-frontend:${Tag}"

Write-Host "Building API image: $ApiImage"
docker build -f "$Root/service/Dockerfile" -t $ApiImage $Root
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Building frontend image: $FrontendImage (NEXT_PUBLIC_API_URL=$FrontendApiUrl)"
docker build `
    -f "$Root/frontend_enterprise/Dockerfile" `
    --build-arg "NEXT_PUBLIC_API_URL=$FrontendApiUrl" `
    -t $FrontendImage `
    "$Root/frontend_enterprise"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($SkipPush) {
    Write-Host "SkipPush set - images built locally only."
    exit 0
}

Write-Host "Pushing $ApiImage"
docker push $ApiImage
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Pushing $FrontendImage"
docker push $FrontendImage
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Done. Share with your team:"
Write-Host "  DOCKERHUB_USER=$DockerHubUser"
Write-Host "  IMAGE_TAG=$Tag"
Write-Host "  docker compose -f docker-compose.hub.yml up -d"
