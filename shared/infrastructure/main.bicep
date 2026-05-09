// foundryLab — Phase 0 infrastructure
// Provisions the shared Foundry account, project, model deployments, and observability.
// All foundryLab agents will share these resources.
//
// Naming convention: foundrylab-<resource>  (per .github/instructions/azure-bicep.instructions.md)
// Region: swedencentral (overrides workspace default — see docs/learnings.md for why)
// Auth: managed identity only — disableLocalAuth=true blocks API keys

targetScope = 'resourceGroup'

@description('Short project key used in resource names')
param projectKey string = 'foundrylab'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Object ID of the user (or service principal) that should get Azure AI Developer access on the project')
param ownerObjectId string

@description('Default chat model to deploy on the Foundry account')
param chatModelName string = 'gpt-4o-mini'

@description('Default chat model version')
param chatModelVersion string = '2024-07-18'

@description('Capacity (thousands of tokens per minute) for the chat deployment')
@minValue(1)
@maxValue(9000)
param chatModelCapacity int = 50

@description('Embedding model used by RAG-style agents (e.g. labMemoryAgent)')
param embedModelName string = 'text-embedding-3-large'

@description('Embedding model version')
param embedModelVersion string = '1'

@description('Capacity for the embedding deployment')
@minValue(1)
@maxValue(2000)
param embedModelCapacity int = 50

@description('Common resource tags')
param tags object = {
  project: 'foundrylab'
  environment: 'shared'
  managedBy: 'bicep'
  costCenter: 'naurolabs-research'
}

// Built-in role IDs
// Azure AI Developer: scope-wide control over agents, evals, datasets in a project
var azureAIDeveloperRoleId = '64702f94-c441-49e6-a78b-ef80e0188fee'
// Cognitive Services OpenAI User: lets a principal call Azure OpenAI inference APIs
var cognitiveServicesOpenAIUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${projectKey}-logs'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${projectKey}-appi'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${projectKey}-mi'
  location: location
  tags: tags
}

// Azure AI Services account — the "Foundry account" (kind: AIServices)
// All foundryLab projects + model deployments hang off this single resource.
resource aiServices 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: '${projectKey}-aiservices'
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${uami.id}': {}
    }
  }
  properties: {
    customSubDomainName: '${projectKey}-aiservices'
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
    allowProjectManagement: true
  }
}

// Foundry project — logical workspace for agents, evaluations, datasets, connections
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: aiServices
  name: projectKey
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: 'NauroLabs Foundry Lab'
    description: 'Shared experimentation project for foundryLab agents'
  }
}

// Chat model deployment (GlobalStandard = pay-per-token, no idle cost)
resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: aiServices
  name: chatModelName
  sku: {
    name: 'GlobalStandard'
    capacity: chatModelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: chatModelName
      version: chatModelVersion
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

// Embedding model deployment — enables RAG for labMemoryAgent
// Sequenced after chatDeployment because parallel deployment of two models on the same
// account sometimes hits a transient 409.
resource embedDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: aiServices
  name: embedModelName
  sku: {
    name: 'GlobalStandard'
    capacity: embedModelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: embedModelName
      version: embedModelVersion
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  dependsOn: [
    chatDeployment
  ]
}

// Diagnostic settings — emit account activity to Log Analytics
resource diag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: aiServices
  name: '${projectKey}-aiservices-diag'
  properties: {
    workspaceId: logs.id
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
      {
        categoryGroup: 'audit'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

// Owner gets full developer access on the project (portal + CLI + SDK)
resource ownerRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: aiServices
  name: guid(aiServices.id, ownerObjectId, azureAIDeveloperRoleId)
  properties: {
    principalId: ownerObjectId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', azureAIDeveloperRoleId)
  }
}

// UAMI gets inference access — agents that run as this identity can call AOAI
resource uamiInferenceRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: aiServices
  name: guid(aiServices.id, uami.id, cognitiveServicesOpenAIUserRoleId)
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUserRoleId)
  }
}

@description('Foundry project endpoint used by SDKs')
output projectEndpoint string = project.properties.endpoints['AI Foundry API']

@description('AI Services account resource ID')
output aiServicesAccountId string = aiServices.id

@description('Foundry project resource ID')
output projectResourceId string = project.id

@description('Chat model deployment name')
output chatDeploymentName string = chatDeployment.name

@description('Embedding model deployment name')
output embedDeploymentName string = embedDeployment.name

@description('App Insights connection string for agent observability')
output appInsightsConnectionString string = appInsights.properties.ConnectionString

@description('Log Analytics workspace resource ID')
output logAnalyticsWorkspaceId string = logs.id

@description('User-assigned managed identity client ID for agent runtimes')
output managedIdentityClientId string = uami.properties.clientId

@description('User-assigned managed identity resource ID')
output managedIdentityResourceId string = uami.id
