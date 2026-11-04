# Going live on Azure

How to put TarangYukti on Azure Container Apps (spec §15.2), first as the **slim demo tier** and later, if real
users are invited, as the full **Tier 1** live-testing environment. Everything is in `infra/azure/` (Bicep),
`docker/` (images) and `.github/workflows/deploy-azure.yml` (continuous deployment).

## What each tier costs and gives

| | Demo tier (`tier=demo`, default) | Tier 1 (`tier=live`) |
|---|---|---|
| Replicas | 0–2 per app (scales to zero when idle; first request after idle takes ~10–30 s) | 2–6 per app |
| Zone redundancy, VNet | No | Yes (chosen at creation, cannot be added later) |
| Front Door + WAF | Optional (`useFrontDoor=true`, ≈ USD 35/month) | Required |
| `ENV` | `preview`: draft languages and phrase files are served | `live`: only approved phrase files and released languages |
| Budget alert | USD 60/month | USD 400/month |
| Expected cost | ≈ USD 20–60/month + Supabase + AuraDB + Gemini | ≈ USD 300–350/month + Pro plans + Gemini |

The demo tier is **not** for real users: `ENV=live` refuses to serve any phrase file that two native speakers have
not approved, and none are approved yet (see `docs/releases.md`).

## One-time setup (≈ 1 hour)

1. **Subscription**: upgrade the Azure account to pay-as-you-go (free trial credit keeps applying until it expires).
   ```bash
   az login && az account set --subscription "<subscription id>"
   for p in Microsoft.App Microsoft.OperationalInsights Microsoft.Cdn Microsoft.Network Microsoft.Insights; do
     az provider register --namespace $p; done
   az group create -n ty-live -l centralindia
   ```
2. **Platform** (registry, Key Vault, identity, logs, environment, monitoring, budget):
   ```bash
   P="tier=demo useFrontDoor=false supabaseUrl=https://<ref>.supabase.co snapshotDate=<YYYY-MM-DD> \
      oncallEmail=<email> budgetStart=$(date +%Y-%m-01)"
   az deployment group create -g ty-live -n main -f infra/azure/main.bicep -p deployApps=false $P
   az deployment group show -g ty-live -n main --query properties.outputs -o table
   ```
3. **Secrets** into Key Vault (give yourself *Key Vault Secrets Officer* on the vault first). Values are the ones in
   your git-ignored `.env`; `redis-url` is `redis://:<redis-password>@ty-redis:6379/0`. Use a **separate VAPID pair**
   for Azure (`npx web-push generate-vapid-keys`).
   ```bash
   for s in google-api-key sarvam-api-key gfw-api-token copernicus-user copernicus-password \
            supabase-service-role-key database-url worker-database-url agent-database-url neo4j-uri neo4j-username \
            neo4j-password vapid-private-key vapid-public-key vapid-subject expo-access-token redis-password redis-url; do
     read -rsp "$s: " v && echo && az keyvault secret set --vault-name "$KV" -n "$s" --value "$v" -o none
   done
   ```
4. **Images** (CI does this on every deploy; by hand the first time). On Windows, build from a clean export of
   the commit (`git archive HEAD | tar -x -C <dir>` plus `apps/app/dist`) — packing the working tree with
   `node_modules` is slow enough for the upload link to expire:
   ```bash
   az acr import --name "$ACR" --source docker.io/library/redis:7.4-alpine --image redis:7.4-alpine
   T=$(git rev-parse --short=12 HEAD)
   for s in agent:apps/agent mcp:services/mcp channels:services/channels worker:services/worker; do
     az acr build -r "$ACR" -t "ty-${s%%:*}:$T" -f docker/Dockerfile.python --build-arg SERVICE_DIR="${s#*:}" .; done
   az acr build -r "$ACR" -t "ty-copilot:$T" -f docker/Dockerfile.copilot .
   EXPO_PUBLIC_COPILOT_URL=<copilotUrl> EXPO_PUBLIC_CHANNELS_URL=<channelsUrl> EXPO_PUBLIC_SUPABASE_URL=<…> \
   EXPO_PUBLIC_SUPABASE_ANON_KEY=<publishable key> EXPO_PUBLIC_VAPID_PUBLIC_KEY=<azure public key> \
     APP_ENV=preview pnpm -C apps/app exec expo export -p web --clear   # --clear: Metro caches inlined values
   az acr build -r "$ACR" -t "ty-web:$T" -f docker/Dockerfile.web .
   ```
5. **Apps and jobs**: `az deployment group create -g ty-live -n main -f infra/azure/main.bicep -p deployApps=true imageTag=$T $P`
6. **Supabase**: Authentication → URL Configuration → Site URL = `webUrl`; add it and `tarangyukti://` to the
   redirect URLs. Google sign-in on the web then works from the Azure host.
7. **Smoke**: `CHANNELS=<channelsUrl> COPILOT=<copilotUrl> WEB=<webUrl> scripts/smoke.sh`

## Continuous deployment

Create an app registration with a federated credential for `repo:Gurjas2112/TarangYukti:environment:live`, give
it *Contributor* on `ty-live` and *AcrPush* on the registry, then set the repository variables listed at the top of
`.github/workflows/deploy-azure.yml` and finally `AZURE_DEPLOY=true`. From then on every green CI run on `main`
builds the images in ACR, deploys new revisions (traffic moves only when probes pass) and runs the smoke test.

## Pausing and tearing down

- Pause between demos: the demo tier already scales to zero; stop the jobs with
  `az containerapp job update -g ty-live -n ty-watch --cron-expression "0 0 1 1 *"` (same for `ty-outbox`).
- Tear down: `az group delete -n ty-live` (the Key Vault stays recoverable for 30 days).

## Before inviting a single real user (Gate LT, spec §15.3)

- [ ] `tier=live`, `useFrontDoor=true`; Supabase **Pro**, Neo4j **AuraDB Professional**
- [ ] Every offered language's phrase file signed by two native speakers (`status: approved`)
- [ ] DPIA (`docs/dpia.md`) completed and signed; real grievance officer in `config/governance.yaml`
- [ ] VAPT by a CERT-In empanelled auditor; findings closed
- [ ] On-call rota + `docs/incident-runbook.md`; SMS paging tested (`oncallPhone`)
- [ ] Restore drill: Supabase backup → scratch project → `make test-rls` and `make kb-query`
- [ ] Gate L1 load test (`tests/load/dawn_rush.py`): 200 users, 15 min, p95 < 2 s, errors < 1 %
