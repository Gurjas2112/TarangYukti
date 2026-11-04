// infra/azure/edge.bicep — Front Door origins and routes, created after the apps exist (spec §15.2.2)
param profileName string
param endpointNames object // { web: '<endpoint name>', copilot: '…', channels: '…' }
param origins object // { web: '<app fqdn>', copilot: '…', channels: '…' }

var names = ['web', 'copilot', 'channels']

resource profile 'Microsoft.Cdn/profiles@2024-02-01' existing = {
  name: profileName
}

resource endpoints 'Microsoft.Cdn/profiles/afdEndpoints@2024-02-01' existing = [
  for n in names: {
    parent: profile
    name: endpointNames[n]
  }
]

resource groups 'Microsoft.Cdn/profiles/originGroups@2024-02-01' = [
  for n in names: {
    parent: profile
    name: 'og-${n}'
    properties: {
      loadBalancingSettings: { sampleSize: 4, successfulSamplesRequired: 3, additionalLatencyInMilliseconds: 50 }
      healthProbeSettings: {
        probePath: n == 'web' ? '/healthz' : '/health'
        probeRequestType: 'HEAD'
        probeProtocol: 'Https'
        probeIntervalInSeconds: 60
      }
    }
  }
]

resource originRes 'Microsoft.Cdn/profiles/originGroups/origins@2024-02-01' = [
  for (n, i) in names: {
    parent: groups[i]
    name: 'o-${n}'
    properties: {
      hostName: origins[n]
      originHostHeader: origins[n]
      httpsPort: 443
      priority: 1
      weight: 1000
      enabledState: 'Enabled'
    }
  }
]

resource routes 'Microsoft.Cdn/profiles/afdEndpoints/routes@2024-02-01' = [
  for (n, i) in names: {
    parent: endpoints[i]
    name: 'r-${n}'
    dependsOn: [originRes[i]]
    properties: {
      originGroup: { id: groups[i].id }
      supportedProtocols: ['Https']
      patternsToMatch: ['/*']
      forwardingProtocol: 'HttpsOnly'
      linkToDefaultDomain: 'Enabled'
      httpsRedirect: 'Enabled'
    }
  }
]
