// infra/azure/job.bicep — one scheduled Container Apps job (schedules are UTC) (spec §15.2.2)
param name string
param location string
param envId string
param identityId string
param registry string
param kvUri string
param image string
param cron string
param cpu string
param memory string
param timeoutSeconds int
param command array
param env array
param secrets array

resource job 'Microsoft.App/jobs@2025-01-01' = {
  name: name
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identityId}': {} } }
  properties: {
    environmentId: envId
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Schedule'
      replicaTimeout: timeoutSeconds
      replicaRetryLimit: 1
      scheduleTriggerConfig: { cronExpression: cron, parallelism: 1, replicaCompletionCount: 1 }
      registries: [{ server: registry, identity: identityId }]
      secrets: [for s in secrets: { name: s, keyVaultUrl: '${kvUri}secrets/${s}', identity: identityId }]
    }
    template: {
      containers: [
        {
          name: name
          image: image
          command: command
          resources: { cpu: json(cpu), memory: memory }
          env: env
        }
      ]
    }
  }
}
