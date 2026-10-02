using './main.bicep'

param projectKey = 'foundrylab'
param location = 'swedencentral'

// Filled in by deploy.ps1 from `az ad signed-in-user show`
param ownerObjectId = ''

param chatModelName = 'gpt-6-luna'
param chatModelVersion = '2026-09-22'
param chatModelCapacity = 100

param premiumChatModelName = 'gpt-6-sol'
param premiumChatModelVersion = '2026-09-22'
param premiumChatModelCapacity = 50

param transcriptionModelName = 'gpt-4o-mini-transcribe'
param transcriptionModelVersion = '2025-12-15'

param embedModelName = 'text-embedding-3-large'
param embedModelVersion = '1'
param embedModelCapacity = 50
