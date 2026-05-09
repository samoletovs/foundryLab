using './main.bicep'

param projectKey = 'foundrylab'
param location = 'swedencentral'

// Filled in by deploy.ps1 from `az ad signed-in-user show`
param ownerObjectId = ''

param chatModelName = 'gpt-4o-mini'
param chatModelVersion = '2024-07-18'
param chatModelCapacity = 50

param embedModelName = 'text-embedding-3-large'
param embedModelVersion = '1'
param embedModelCapacity = 50
