// infra/azure/app.bicep — one container app: identity, registry, Key Vault secrets, probes, scaling (spec §15.2.2)
param name string
param location string
param envId string
param identityId string
param registry string
param kvUri string
param image string
param cpu string
param memory string
param port int
param external bool
param transport string = 'auto'
param minReplicas int = 1
param maxReplicas int = 3
param command array = []
param env array
param secrets array
param corsOrigins array = []
param probePath string

resource app 'Microsoft.App/containerApps@2025-01-01' = {
  name: name
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identityId}': {} } }
  properties: {
    environmentId: envId
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: external
        targetPort: port
        transport: transport
        exposedPort: transport == 'tcp' ? port : null
        allowInsecure: false
        corsPolicy: empty(corsOrigins)
          ? null
          : {
              allowedOrigins: corsOrigins
              allowedMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
              allowedHeaders: ['*']
            }
      }
      registries: [{ server: registry, identity: identityId }]
      secrets: [for s in secrets: { name: s, keyVaultUrl: '${kvUri}secrets/${s}', identity: identityId }]
    }
    template: {
      containers: [
        {
          name: name
          image: image
          command: empty(command) ? null : command
          resources: { cpu: json(cpu), memory: memory }
          env: env
          probes: empty(probePath)
            ? [{ type: 'Liveness', tcpSocket: { port: port } }]
            : [
                { type: 'Liveness', httpGet: { path: probePath, port: port } }
                { type: 'Readiness', httpGet: { path: probePath, port: port } }
              ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: transport == 'tcp' ? [] : [{ name: 'http', http: { metadata: { concurrentRequests: '20' } } }]
      }
    }
  }
}

output fqdn string = external ? app.properties.configuration.ingress.fqdn : ''
