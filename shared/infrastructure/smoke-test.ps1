$ErrorActionPreference = 'Stop'
$token = az account get-access-token --resource https://cognitiveservices.azure.com --query accessToken -o tsv
$body = @{
  messages = @(@{ role = 'user'; content = 'Reply with exactly: foundryLab is alive' })
  max_tokens = 20
  temperature = 0
} | ConvertTo-Json -Depth 5 -Compress

$resp = Invoke-RestMethod `
  -Method Post `
  -Uri 'https://foundrylab-aiservices.openai.azure.com/openai/deployments/gpt-4o-mini/chat/completions?api-version=2024-10-21' `
  -Headers @{ Authorization = "Bearer $token"; 'Content-Type' = 'application/json' } `
  -Body $body

Write-Host "Model said: $($resp.choices[0].message.content)" -ForegroundColor Green
Write-Host "Tokens used: prompt=$($resp.usage.prompt_tokens) completion=$($resp.usage.completion_tokens)"
