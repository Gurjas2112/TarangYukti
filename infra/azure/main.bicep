// infra/azure/main.bicep — TarangYukti on Azure Container Apps, Central India (spec §15.2.2).
//
// tier = 'demo' (default, the slim hosted demo the owner chose): apps scale to zero, no VNet / zone redundancy,
//        Front Door optional (useFrontDoor), ENV=preview so draft languages are served, smaller budget.
// tier = 'live' (spec Tier 1 for live testing with real users): ≥ 2 replicas, zone-redundant environment in a VNet,
//        Front Door Standard + WAF required, ENV=live (only approved phrase files and released languages).
//
// Two runs: deployApps=false creates the platform; after secrets and images exist, deployApps=true adds the apps,
// jobs and (with Front Door) the routes. Validate with `az bicep build` and `az deployment group what-if`.
@allowed(['demo', 'live'])
param tier string = 'demo'
param useFrontDoor bool = tier == 'live'
param location string = 'centralindia'
param deployApps bool = false
param imageTag string = 'bootstrap'
param supabaseUrl string
param snapshotDate string
param oncallEmail string
@description('10-digit Indian mobile for SMS alerts; empty = e-mail only')
param oncallPhone string = ''
param budgetAmount int = tier == 'live' ? 400 : 60
param budgetStart string // first day of the current month, e.g. 2026-11-01

var live = tier == 'live'
var sfx = uniqueString(resourceGroup().id)
var acrPullRole = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var kvSecretsUserRole = '4633458b-17de-408a-b874-0445c86b69e6'
var minReplicas = live ? 2 : 0

resource id 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'ty-id'
  location: location
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'tyacr${sfx}'
  location: location
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, id.id, 'acrpull')
  properties: {
    principalId: id.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRole)
  }
}

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'ty-kv-${take(sfx, 12)}'
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 30
    enablePurgeProtection: true
  }
}

resource kvRead 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: kv
  name: guid(kv.id, id.id, 'kvsecrets')
  properties: {
    principalId: id.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUserRole)
  }
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'ty-logs'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 180 // CERT-In: ICT logs kept 180 days, in India
    workspaceCapping: { dailyQuotaGb: live ? 2 : 1 }
  }
}

// zone redundancy needs a VNet and is fixed when the environment is created — live tier only
resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = if (live) {
  name: 'ty-vnet'
  location: location
  properties: {
    addressSpace: { addressPrefixes: ['10.40.0.0/16'] }
    subnets: [
      {
        name: 'aca'
        properties: {
          addressPrefix: '10.40.0.0/23'
          delegations: [{ name: 'aca', properties: { serviceName: 'Microsoft.App/environments' } }]
        }
      }
    ]
  }
}

resource env 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: 'ty-env'
  location: location
  properties: {
    zoneRedundant: live
    vnetConfiguration: live ? { infrastructureSubnetId: vnet!.properties.subnets[0].id, internal: false } : null
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      { name: 'Consumption', workloadProfileType: 'Consumption' }
    ]
  }
}

// ---- Front Door profile, endpoints and WAF (optional in the demo tier)
resource fd 'Microsoft.Cdn/profiles@2024-02-01' = if (useFrontDoor) {
  name: 'ty-fd'
  location: 'global'
  sku: { name: 'Standard_AzureFrontDoor' }
}

resource fdWeb 'Microsoft.Cdn/profiles/afdEndpoints@2024-02-01' = if (useFrontDoor) {
  parent: fd
  name: 'ty-web-${take(sfx, 8)}'
  location: 'global'
  properties: { enabledState: 'Enabled' }
}

resource fdCopilot 'Microsoft.Cdn/profiles/afdEndpoints@2024-02-01' = if (useFrontDoor) {
  parent: fd
  name: 'ty-copilot-${take(sfx, 8)}'
  location: 'global'
  properties: { enabledState: 'Enabled' }
}

resource fdChannels 'Microsoft.Cdn/profiles/afdEndpoints@2024-02-01' = if (useFrontDoor) {
  parent: fd
  name: 'ty-channels-${take(sfx, 8)}'
  location: 'global'
  properties: { enabledState: 'Enabled' }
}

resource waf 'Microsoft.Network/FrontDoorWebApplicationFirewallPolicies@2024-02-01' = if (useFrontDoor) {
  name: 'tywaf'
  location: 'global'
  sku: { name: 'Standard_AzureFrontDoor' }
  properties: {
    policySettings: { enabledState: 'Enabled', mode: 'Prevention' }
    customRules: {
      rules: [
        {
          name: 'ratePerIp'
          priority: 10
          enabledState: 'Enabled'
          ruleType: 'RateLimitRule'
          rateLimitDurationInMinutes: 1
          rateLimitThreshold: 300
          matchConditions: [
            { matchVariable: 'RequestUri', operator: 'BeginsWith', matchValue: ['/'] }
          ]
          action: 'Block'
        }
        {
          name: 'adminOnlyFromIndia'
          priority: 20
          enabledState: 'Enabled'
          ruleType: 'MatchRule'
          matchConditions: [
            { matchVariable: 'RequestUri', operator: 'Contains', matchValue: ['/admin'] }
            { matchVariable: 'SocketAddr', operator: 'GeoMatch', negateCondition: true, matchValue: ['IN'] }
          ]
          action: 'Block'
        }
      ]
    }
  }
}

resource wafLink 'Microsoft.Cdn/profiles/securityPolicies@2024-02-01' = if (useFrontDoor) {
  parent: fd
  name: 'waf'
  properties: {
    parameters: {
      type: 'WebApplicationFirewall'
      wafPolicy: { id: waf.id }
      associations: [
        {
          domains: [{ id: fdWeb.id }, { id: fdCopilot.id }, { id: fdChannels.id }]
          patternsToMatch: ['/*']
        }
      ]
    }
  }
}

// public URLs: Front Door hosts, or the apps' own Container Apps hosts in the demo tier
var appDomain = env.properties.defaultDomain
var webOrigin = useFrontDoor ? 'https://${fdWeb!.properties.hostName}' : 'https://ty-web.${appDomain}'
var copilotUrl = useFrontDoor ? 'https://${fdCopilot!.properties.hostName}' : 'https://ty-copilot.${appDomain}'
var channelsUrl = useFrontDoor ? 'https://${fdChannels!.properties.hostName}' : 'https://ty-channels.${appDomain}'
var frontDoorId = useFrontDoor ? fd!.properties.frontDoorId : ''

module monitor 'monitor.bicep' = {
  name: 'ty-monitor'
  params: {
    location: location
    workspaceId: logs.id
    healthUrl: '${channelsUrl}/health'
    oncallEmail: oncallEmail
    oncallPhone: oncallPhone
    budgetAmount: budgetAmount
    budgetStart: budgetStart
  }
}

var img = acr.properties.loginServer

var settings = [
  { name: 'ENV', value: live ? 'live' : 'preview' } // live serves only approved phrases and released languages
  { name: 'ORCA_MODEL', value: 'gemini-3.8-flash' }
  { name: 'ORCA_PLANNER_EFFORT', value: 'low' }
  { name: 'EMBED_MODEL', value: 'gemini-embedding-2' }
  { name: 'EMBED_DIM', value: '768' }
  { name: 'DATA_MODE', value: 'online' }
  { name: 'SNAPSHOT_DATE', value: snapshotDate }
  { name: 'RAG_MIN_SIM', value: '0.70' } // calibrated on the golden set (docs/eval-report.md)
  { name: 'WEB_ORIGIN', value: webOrigin }
  { name: 'SUPABASE_URL', value: supabaseUrl }
  { name: 'MCP_URL', value: 'http://ty-mcp/mcp' }
  { name: 'AGENT_URL', value: 'http://ty-agent' }
  { name: 'FRONTDOOR_ID', value: frontDoorId }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: monitor.outputs.connectionString }
  { name: 'GOOGLE_API_KEY', secretRef: 'google-api-key' }
  { name: 'REDIS_URL', secretRef: 'redis-url' }
  { name: 'DATABASE_URL', secretRef: 'database-url' }
  { name: 'SUPABASE_SERVICE_ROLE_KEY', secretRef: 'supabase-service-role-key' }
  { name: 'NEO4J_URI', secretRef: 'neo4j-uri' }
  { name: 'NEO4J_USERNAME', secretRef: 'neo4j-username' }
  { name: 'NEO4J_PASSWORD', secretRef: 'neo4j-password' }
]
var common = [
  'google-api-key'
  'redis-url'
  'database-url'
  'supabase-service-role-key'
  'neo4j-uri'
  'neo4j-username'
  'neo4j-password'
]
var dataEnv = [
  { name: 'GFW_API_TOKEN', secretRef: 'gfw-api-token' }
  { name: 'COPERNICUSMARINE_SERVICE_USERNAME', secretRef: 'copernicus-user' }
  { name: 'COPERNICUSMARINE_SERVICE_PASSWORD', secretRef: 'copernicus-password' }
]
var dataSecrets = [
  'gfw-api-token'
  'copernicus-user'
  'copernicus-password'
]
var pushEnv = [
  { name: 'WORKER_DATABASE_URL', secretRef: 'worker-database-url' }
  { name: 'VAPID_PRIVATE_KEY', secretRef: 'vapid-private-key' }
  { name: 'VAPID_PUBLIC_KEY', secretRef: 'vapid-public-key' }
  { name: 'VAPID_SUBJECT', secretRef: 'vapid-subject' }
  { name: 'EXPO_ACCESS_TOKEN', secretRef: 'expo-access-token' }
]
var pushSecrets = [
  'worker-database-url'
  'vapid-private-key'
  'vapid-public-key'
  'vapid-subject'
  'expo-access-token'
]
var sarvamEnv = [{ name: 'SARVAM_API_KEY', secretRef: 'sarvam-api-key' }]

module web 'app.bicep' = if (deployApps) {
  name: 'ty-web'
  params: {
    name: 'ty-web'
    location: location
    envId: env.id
    identityId: id.id
    registry: img
    kvUri: kv.properties.vaultUri
    image: '${img}/ty-web:${imageTag}'
    cpu: '0.25'
    memory: '0.5Gi'
    port: 8080
    external: true
    minReplicas: minReplicas
    maxReplicas: live ? 4 : 2
    env: [{ name: 'FRONTDOOR_ID', value: frontDoorId }]
    secrets: []
    probePath: '/healthz'
  }
}

module copilot 'app.bicep' = if (deployApps) {
  name: 'ty-copilot'
  params: {
    name: 'ty-copilot'
    location: location
    envId: env.id
    identityId: id.id
    registry: img
    kvUri: kv.properties.vaultUri
    image: '${img}/ty-copilot:${imageTag}'
    cpu: '0.5'
    memory: '1Gi'
    port: 8200
    external: true
    minReplicas: minReplicas
    maxReplicas: live ? 6 : 2
    corsOrigins: [webOrigin]
    env: [
      { name: 'AGENT_URL', value: 'http://ty-agent' }
      { name: 'PORT', value: '8200' }
      { name: 'FRONTDOOR_ID', value: frontDoorId }
      { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: monitor.outputs.connectionString }
    ]
    secrets: []
    probePath: '/health'
  }
}

module channels 'app.bicep' = if (deployApps) {
  name: 'ty-channels'
  params: {
    name: 'ty-channels'
    location: location
    envId: env.id
    identityId: id.id
    registry: img
    kvUri: kv.properties.vaultUri
    image: '${img}/ty-channels:${imageTag}'
    cpu: '0.5'
    memory: '1Gi'
    port: 8002
    external: true
    minReplicas: minReplicas
    maxReplicas: live ? 6 : 2
    corsOrigins: [webOrigin]
    command: ['uvicorn', 'ty_channels.app:app', '--host', '0.0.0.0', '--port', '8002']
    env: concat(settings, sarvamEnv)
    secrets: concat(common, ['sarvam-api-key'])
    probePath: '/health'
  }
}

module agent 'app.bicep' = if (deployApps) {
  name: 'ty-agent'
  params: {
    name: 'ty-agent'
    location: location
    envId: env.id
    identityId: id.id
    registry: img
    kvUri: kv.properties.vaultUri
    image: '${img}/ty-agent:${imageTag}'
    cpu: '0.5'
    memory: '1Gi'
    port: 8123
    external: false
    minReplicas: minReplicas
    maxReplicas: live ? 6 : 2
    command: ['uvicorn', 'server:app', '--host', '0.0.0.0', '--port', '8123', '--workers', '1']
    env: concat(settings, sarvamEnv, [{ name: 'AGENT_DATABASE_URL', secretRef: 'agent-database-url' }])
    secrets: concat(common, ['sarvam-api-key', 'agent-database-url'])
    probePath: '/ok'
  }
}

module mcp 'app.bicep' = if (deployApps) {
  name: 'ty-mcp'
  params: {
    name: 'ty-mcp'
    location: location
    envId: env.id
    identityId: id.id
    registry: img
    kvUri: kv.properties.vaultUri
    image: '${img}/ty-mcp:${imageTag}'
    cpu: '1'
    memory: '2Gi'
    port: 8001
    external: false
    minReplicas: minReplicas
    maxReplicas: live ? 4 : 2
    command: ['python', '-m', 'tarangyukti.server']
    env: concat(settings, dataEnv, [{ name: 'PORT', value: '8001' }])
    secrets: concat(common, dataSecrets)
    probePath: '' // TCP probe
  }
}

module redis 'app.bicep' = if (deployApps) {
  name: 'ty-redis'
  params: {
    name: 'ty-redis'
    location: location
    envId: env.id
    identityId: id.id
    registry: img
    kvUri: kv.properties.vaultUri
    image: '${img}/redis:7.4-alpine'
    cpu: '0.25'
    memory: '0.5Gi'
    port: 6379
    external: false
    transport: 'tcp'
    minReplicas: 1 // TCP apps do not wake from zero; cache only, no persistence
    maxReplicas: 1
    command: [
      'sh'
      '-c'
      'exec redis-server --requirepass "$REDIS_PASSWORD" --maxmemory 400mb --maxmemory-policy allkeys-lru --save "" --appendonly no'
    ]
    env: [{ name: 'REDIS_PASSWORD', secretRef: 'redis-password' }]
    secrets: ['redis-password']
    probePath: ''
  }
}

var jobs = [
  { name: 'ty-watch', cron: '*/15 * * * *', cpu: '0.5', memory: '1Gi', timeout: 600, cmd: ['python', '-m', 'ty_worker.watch_once'] }
  { name: 'ty-outbox', cron: '* * * * *', cpu: '0.25', memory: '0.5Gi', timeout: 55, cmd: ['python', '-m', 'ty_worker.outbox'] }
  { name: 'ty-ingest', cron: '30 20 * * *', cpu: '1', memory: '2Gi', timeout: 3600, cmd: ['python', '-m', 'ty_worker.ingest_once'] } // 02:00 IST
  {
    name: 'ty-nightly' // 02:30 IST: 30-day thread purge, deletions after the 7-day undo, retention
    cron: '0 21 * * *'
    cpu: '0.5'
    memory: '1Gi'
    timeout: 1800
    cmd: ['sh', '-c', 'python -m ty_worker.agent_purge && python -m ty_worker.housekeeping']
  }
]

module workerJobs 'job.bicep' = [for j in jobs: if (deployApps) {
  name: j.name
  params: {
    name: j.name
    location: location
    envId: env.id
    identityId: id.id
    registry: img
    kvUri: kv.properties.vaultUri
    image: '${img}/ty-worker:${imageTag}'
    cron: j.cron
    cpu: j.cpu
    memory: j.memory
    timeoutSeconds: j.timeout
    command: j.cmd
    env: concat(settings, dataEnv, pushEnv)
    secrets: concat(common, dataSecrets, pushSecrets)
  }
}]

module edge 'edge.bicep' = if (deployApps && useFrontDoor) {
  name: 'ty-edge'
  params: {
    profileName: 'ty-fd'
    endpointNames: {
      web: 'ty-web-${take(sfx, 8)}'
      copilot: 'ty-copilot-${take(sfx, 8)}'
      channels: 'ty-channels-${take(sfx, 8)}'
    }
    origins: {
      web: web!.outputs.fqdn
      copilot: copilot!.outputs.fqdn
      channels: channels!.outputs.fqdn
    }
  }
}

output acrName string = acr.name
output keyVaultName string = kv.name
output webUrl string = webOrigin
output copilotUrl string = copilotUrl
output channelsUrl string = channelsUrl
output frontDoorId string = frontDoorId
