# Deployment runbook: Azure Container Apps

One container, always on, 2 vCPU / 4 GiB, no state. Commands are Azure CLI; run them from the
repository root after `az login`. Names are examples; keep them lowercase.

## 0. Prerequisites (once)

```bash
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
az provider register --namespace Microsoft.ContainerRegistry
```

## 1. Resource group and registry

```bash
LOCATION=eastus
RG=label-check-rg
ACR=labelcheckacr$RANDOM          # must be globally unique, lowercase, 5-50 chars
az group create --name $RG --location $LOCATION
az acr create --name $ACR --resource-group $RG --sku Basic
```

## 2. Get the image into the registry

ACR's cloud build (`az acr build`) is disabled on new subscriptions until a support request is
approved. CI builds the same image on every push to `master`, verifies it, and pushes it to the
registry as `label-check:<short sha>` and `label-check:latest`, using three repository secrets:
`ACR_LOGIN_SERVER`, `ACR_USERNAME`, `ACR_PASSWORD` (registry admin credentials; a service principal
with `AcrPush` is the production-grade alternative).

```bash
az acr update --name $ACR --admin-enabled true
az acr credential show --name $ACR     # username + password -> GitHub secrets
```

If ACR Tasks are available on the subscription, `az acr build --registry $ACR --image label-check:$SHA --build-arg GIT_SHA=$SHA .` does the same from the repository root.

## 3. Environment and app

```bash
ENV=label-check-env
APP=label-check
az containerapp env create --name $ENV --resource-group $RG --location $LOCATION
az containerapp create \
  --name $APP --resource-group $RG --environment $ENV \
  --image $ACR.azurecr.io/label-check:$SHA \
  --registry-server $ACR.azurecr.io --registry-identity system \
  --target-port 8000 --ingress external \
  --cpu 2 --memory 4Gi --min-replicas 1 --max-replicas 1 \
  --env-vars TTB_OCR_WORKERS=2 TTB_TRUST_PROXY=true GIT_SHA=$SHA TTB_OCR_MAX_SIDE=1280
az containerapp show --name $APP --resource-group $RG --query properties.configuration.ingress.fqdn -o tsv
```

`--registry-identity system` gives the app a managed identity with pull rights on the registry, so
no registry password is stored anywhere.

## 4. Probes (readiness gates traffic until the models are warm)

```bash
az containerapp update --name $APP --resource-group $RG --yaml - <<'YAML'
properties:
  template:
    containers:
      - name: label-check
        probes:
          - type: Startup
            httpGet: { path: /api/v1/ready, port: 8000 }
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 30
          - type: Readiness
            httpGet: { path: /api/v1/ready, port: 8000 }
            periodSeconds: 10
          - type: Liveness
            httpGet: { path: /api/v1/health, port: 8000 }
            periodSeconds: 30
YAML
```

(If the YAML update complains about the container name, take it from
`az containerapp show ... --query properties.template.containers[0].name`.)

## 5. Verify from outside

```bash
FQDN=$(az containerapp show --name $APP --resource-group $RG --query properties.configuration.ingress.fqdn -o tsv)
curl -s https://$FQDN/api/v1/health | python -m json.tool
python tools/loadtest.py --url https://$FQDN --mode steady --endpoint verify --n 20
python tools/loadtest.py --url https://$FQDN --mode steady --endpoint extract --n 100
python tools/loadtest.py --url https://$FQDN --mode burst --endpoint extract --concurrency 16
```

Record the numbers in the README "Measured" section and keep `docs/LOADTEST.md`.

## 6. Custom domain (so the submitted URL survives a later move)

1. In the DNS provider: `CNAME labelcheck.example -> <FQDN>` and
   `TXT asuid.labelcheck.example -> <verification id>` where the id comes from
   `az containerapp show ... --query properties.customDomainVerificationId -o tsv`.
2. Bind with a free managed certificate:

```bash
DOMAIN=labelcheck.example
az containerapp hostname add  --name $APP --resource-group $RG --hostname $DOMAIN
az containerapp hostname bind --name $APP --resource-group $RG --hostname $DOMAIN --environment $ENV --validation-method CNAME
```

Certificate issuance takes a few minutes. Test `https://$DOMAIN/api/v1/health`.

## 7. Redeploy

Push to `master`, let CI build, verify and publish `label-check:<short sha>`, then point the app at it:

```bash
SHA=$(git rev-parse --short HEAD)
az containerapp update --name $APP --resource-group $RG --image $ACR.azurecr.io/label-check:$SHA --set-env-vars GIT_SHA=$SHA
```

The footer and `/api/v1/health` show the SHA, so a reviewer can match the running build to the tag.

## 8. Freeze, monitor, cost

- Tag the submitted commit: `git tag -a v1.0-submitted -m "Submitted" && git push --tags`.
  No deploys after that.
- Health monitor: any uptime checker on `https://$DOMAIN/api/v1/health` every 5 minutes.
- Cost: with `min-replicas 1` the app is billed continuously (idle rate when no requests are being
  served). Check the subscription's cost analysis after 24 hours and note the real figure in the
  decision log. Stop billing after the review with `az containerapp update --min-replicas 0` or
  delete the resource group.

## Notes

- Multipart parts up to the per-image cap stay in memory (`app/main.py` raises Starlette's spool
  threshold); a larger part is spooled to `/tmp` until the route rejects it. Mount `/tmp` in memory
  where the platform allows it (Container Apps: an ephemeral volume; Docker: `--tmpfs /tmp`).
- The image needs no outbound network at run time. If the environment restricts egress, nothing
  in the app will notice.
- Two vCPUs are the floor for the five-second front+back target; more vCPUs raise batch throughput
  linearly (`TTB_OCR_WORKERS` defaults to the CPU count).
