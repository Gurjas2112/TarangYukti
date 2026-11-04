// infra/azure/monitor.bicep — Application Insights, on-call action group, availability test, alerts, budget
// (spec §15.2.2). SMS paging only when a phone number is given.
param location string
param workspaceId string
param healthUrl string // https://<channels public host>/health
param oncallEmail string
param oncallPhone string = '' // 10-digit Indian mobile number, without +91
param budgetAmount int = 400
param budgetStart string // first day of the current month, e.g. 2026-11-01

resource ai 'Microsoft.Insights/components@2020-02-02' = {
  name: 'ty-ai'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspaceId
    IngestionMode: 'LogAnalytics'
    DisableLocalAuth: false
  }
}

resource oncall 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'ty-oncall'
  location: 'global'
  properties: {
    groupShortName: 'ty-oncall'
    enabled: true
    emailReceivers: [{ name: 'oncall-email', emailAddress: oncallEmail, useCommonAlertSchema: true }]
    smsReceivers: empty(oncallPhone) ? [] : [{ name: 'oncall-sms', countryCode: '91', phoneNumber: oncallPhone }]
  }
}

resource health 'Microsoft.Insights/webtests@2022-06-15' = {
  name: 'ty-health'
  location: location
  kind: 'standard'
  tags: { 'hidden-link:${ai.id}': 'Resource' }
  properties: {
    SyntheticMonitorId: 'ty-health'
    Name: 'ty-channels health'
    Kind: 'standard'
    Enabled: true
    Frequency: 300
    Timeout: 30
    RetryEnabled: true
    Locations: [
      { Id: 'apac-sg-sin-azr' }
      { Id: 'apac-hk-hkn-azr' }
      { Id: 'apac-jp-kaw-edge' }
    ]
    Request: { RequestUrl: healthUrl, HttpVerb: 'GET' }
    ValidationRules: { ExpectedHttpStatusCode: 200, SSLCheck: true, SSLCertRemainingLifetimeCheck: 7 }
  }
}

resource availabilityAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'ty-health-down'
  location: 'global'
  properties: {
    description: 'Public health check failing from 2 or more locations'
    severity: 1
    enabled: true
    scopes: [health.id, ai.id]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.WebtestLocationAvailabilityCriteria'
      webTestId: health.id
      componentId: ai.id
      failedLocationCount: 2
    }
    actions: [{ actionGroupId: oncall.id }]
  }
}

resource failedRequests 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'ty-failed-requests'
  location: 'global'
  properties: {
    description: 'More than 20 failed requests in 5 minutes'
    severity: 2
    enabled: true
    scopes: [ai.id]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'failed'
          criterionType: 'StaticThresholdCriterion'
          metricNamespace: 'microsoft.insights/components'
          metricName: 'requests/failed'
          operator: 'GreaterThan'
          threshold: 20
          timeAggregation: 'Count'
        }
      ]
    }
    actions: [{ actionGroupId: oncall.id }]
  }
}

resource budget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: 'ty-budget'
  properties: {
    category: 'Cost'
    amount: budgetAmount
    timeGrain: 'Monthly'
    timePeriod: { startDate: budgetStart }
    notifications: {
      actual80: { enabled: true, operator: 'GreaterThan', threshold: 80, thresholdType: 'Actual', contactEmails: [oncallEmail] }
      forecast100: { enabled: true, operator: 'GreaterThan', threshold: 100, thresholdType: 'Forecasted', contactEmails: [oncallEmail] }
    }
  }
}

output connectionString string = ai.properties.ConnectionString
