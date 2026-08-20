#!/usr/bin/env bash
# ============================================================
# FinSight LLMOps — Azure Container Apps Deployment Script
# ============================================================
# Deploys a three-service architecture, all in one Container Apps environment:
#   finsight-ollama — Ollama, serving Llama 3 (CPU-only — see note below)
#   finsight-api    — FastAPI REST API (agent, guardrails, RAG, DB, PDF reports)
#   finsight-ui     — Streamlit frontend, pure HTTP client of finsight-api
# api and ui run from the SAME image with different `--command` overrides.
#
# IMPORTANT — CPU-only Ollama: Azure Container Apps only runs Llama 3 on CPU
# unless you enable GPU workload profiles (a separate, pricier environment
# type: NC A100 v4 profiles). An 8B model on generic Container Apps vCPUs is
# meaningfully slower than local GPU/Apple-silicon inference — expect single
# queries (each is 2-4+ LLM calls: agent reasoning + 2 guardrail checks) to
# take low minutes rather than the ~10-30s seen in local testing. This script
# does not set up GPU profiles; add that yourself if you need faster inference.
#
# Prerequisites:
#   - Azure CLI (az) installed and authenticated (this script runs `az login`)
#   - Docker installed and running
#   - Run this from your own machine — az login is interactive, and this
#     creates real, billed Azure resources.
# ============================================================

set -euo pipefail

# --- Configuration ---
RESOURCE_GROUP="finsight-rg"
LOCATION="eastus"
REGISTRY_NAME="finsightregistry"       # Must be globally unique — change if taken
IMAGE_NAME="finsight-llmops"
IMAGE_TAG="v2"
API_APP_NAME="finsight-api"
UI_APP_NAME="finsight-ui"
OLLAMA_APP_NAME="finsight-ollama"
CONTAINER_APP_ENV="finsight-env"
OLLAMA_MODEL="llama3"

# Set to "false" to skip Azure Files persistence for Ollama's model cache —
# simpler, but every cold start / redeploy re-pulls the ~4.7GB model.
PERSIST_OLLAMA_MODELS="true"
STORAGE_ACCOUNT="finsightollamastore"   # Must be globally unique, lowercase, no dashes
FILE_SHARE_NAME="ollama-models"
ENV_STORAGE_NAME="ollama-models"

echo "=================================================="
echo "  FinSight LLMOps — Azure Deployment (ollama + api + ui)"
echo "=================================================="

# Step 1: Login to Azure
echo ""
echo "[1/11] Logging in to Azure..."
az login

# Step 2: Create resource group
echo ""
echo "[2/11] Creating resource group '$RESOURCE_GROUP' in '$LOCATION'..."
az group create \
    --name "$RESOURCE_GROUP" \
    --location "$LOCATION"

# Step 3: Create Azure Container Registry (ACR)
echo ""
echo "[3/11] Creating Azure Container Registry '$REGISTRY_NAME'..."
az acr create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$REGISTRY_NAME" \
    --sku Basic \
    --admin-enabled true

# Step 4: Build & push the shared image (used for both api and ui)
echo ""
echo "[4/11] Building and pushing '$IMAGE_NAME:$IMAGE_TAG' to ACR..."
az acr login --name "$REGISTRY_NAME"
docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" .
REGISTRY_URL="${REGISTRY_NAME}.azurecr.io"
docker tag "${IMAGE_NAME}:${IMAGE_TAG}" "${REGISTRY_URL}/${IMAGE_NAME}:${IMAGE_TAG}"
docker push "${REGISTRY_URL}/${IMAGE_NAME}:${IMAGE_TAG}"
ACR_PASSWORD=$(az acr credential show --name "$REGISTRY_NAME" --query passwords[0].value -o tsv)

# Step 5: Create the Container Apps environment
echo ""
echo "[5/11] Creating Azure Container Apps environment..."
az containerapp env create \
    --name "$CONTAINER_APP_ENV" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION"

# Step 6 (optional): Azure Files share so Ollama doesn't re-pull the model on every restart
if [ "$PERSIST_OLLAMA_MODELS" = "true" ]; then
    echo ""
    echo "[6/11] Setting up Azure Files persistence for Ollama's model cache..."
    az storage account create \
        --name "$STORAGE_ACCOUNT" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --sku Standard_LRS \
        --kind StorageV2

    STORAGE_KEY=$(az storage account keys list \
        --account-name "$STORAGE_ACCOUNT" \
        --resource-group "$RESOURCE_GROUP" \
        --query "[0].value" -o tsv)

    az storage share-rm create \
        --storage-account "$STORAGE_ACCOUNT" \
        --name "$FILE_SHARE_NAME" \
        --quota 50

    az containerapp env storage set \
        --name "$CONTAINER_APP_ENV" \
        --resource-group "$RESOURCE_GROUP" \
        --storage-name "$ENV_STORAGE_NAME" \
        --azure-file-account-name "$STORAGE_ACCOUNT" \
        --azure-file-account-key "$STORAGE_KEY" \
        --azure-file-share-name "$FILE_SHARE_NAME" \
        --access-mode ReadWrite
else
    echo ""
    echo "[6/11] Skipping Azure Files persistence (PERSIST_OLLAMA_MODELS=false)."
fi

# Step 7: Deploy Ollama (internal-only ingress — only finsight-api needs to reach it)
echo ""
echo "[7/11] Deploying '$OLLAMA_APP_NAME'..."
if [ "$PERSIST_OLLAMA_MODELS" = "true" ]; then
    # Volume mounts aren't exposed as simple `create` flags, so this app is
    # defined via an inline YAML manifest instead.
    OLLAMA_YAML=$(mktemp)
    cat > "$OLLAMA_YAML" <<EOF
properties:
  managedEnvironmentId: $(az containerapp env show --name "$CONTAINER_APP_ENV" --resource-group "$RESOURCE_GROUP" --query id -o tsv)
  configuration:
    ingress:
      external: false
      targetPort: 11434
  template:
    containers:
      - image: ollama/ollama:latest
        name: ollama
        resources:
          cpu: 4
          memory: 8Gi
        volumeMounts:
          - volumeName: ollama-models-vol
            mountPath: /root/.ollama
    volumes:
      - name: ollama-models-vol
        storageType: AzureFile
        storageName: $ENV_STORAGE_NAME
    scale:
      minReplicas: 1
      maxReplicas: 1
EOF
    az containerapp create \
        --name "$OLLAMA_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --environment "$CONTAINER_APP_ENV" \
        --yaml "$OLLAMA_YAML"
    rm -f "$OLLAMA_YAML"
else
    az containerapp create \
        --name "$OLLAMA_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --environment "$CONTAINER_APP_ENV" \
        --image "ollama/ollama:latest" \
        --target-port 11434 \
        --ingress internal \
        --cpu 4 --memory 8Gi \
        --min-replicas 1 --max-replicas 1
fi

# Step 8: Pull the model into the running Ollama container
echo ""
echo "[8/11] Pulling '$OLLAMA_MODEL' into Ollama (this can take several minutes)..."
az containerapp exec \
    --name "$OLLAMA_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --command "ollama pull ${OLLAMA_MODEL}" \
    || echo "  (If exec failed because the revision wasn't ready yet, re-run: az containerapp exec --name $OLLAMA_APP_NAME --resource-group $RESOURCE_GROUP --command 'ollama pull ${OLLAMA_MODEL}')"

# Ollama is reachable from other apps in the same environment at http://<app-name>
OLLAMA_INTERNAL_URL="http://${OLLAMA_APP_NAME}"

# Step 9: Deploy the API service (the UI needs its URL, deployed next)
echo ""
echo "[9/11] Deploying '$API_APP_NAME'..."
az containerapp create \
    --name "$API_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --environment "$CONTAINER_APP_ENV" \
    --image "${REGISTRY_URL}/${IMAGE_NAME}:${IMAGE_TAG}" \
    --registry-server "${REGISTRY_URL}" \
    --registry-username "$REGISTRY_NAME" \
    --registry-password "$ACR_PASSWORD" \
    --command "uvicorn" "backend.api:app" "--host" "0.0.0.0" "--port" "8000" "--workers" "2" "--timeout-keep-alive" "600" \
    --target-port 8000 \
    --ingress external \
    --cpu 2 --memory 4Gi \
    --min-replicas 1 --max-replicas 3 \
    --env-vars \
        "OLLAMA_HOST=${OLLAMA_INTERNAL_URL}" \
        "OLLAMA_MODEL=${OLLAMA_MODEL}" \
        "CHROMA_DB_PATH=/app/chroma_db" \
        "DATABASE_URL=sqlite:////app/finsight.db"

API_URL=$(az containerapp show \
    --name "$API_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query properties.configuration.ingress.fqdn \
    -o tsv)

# Step 10: Deploy the UI service, pointed at the API's URL
echo ""
echo "[10/11] Deploying '$UI_APP_NAME' (API_BASE_URL=https://${API_URL})..."
az containerapp create \
    --name "$UI_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --environment "$CONTAINER_APP_ENV" \
    --image "${REGISTRY_URL}/${IMAGE_NAME}:${IMAGE_TAG}" \
    --registry-server "${REGISTRY_URL}" \
    --registry-username "$REGISTRY_NAME" \
    --registry-password "$ACR_PASSWORD" \
    --target-port 8501 \
    --ingress external \
    --cpu 1 --memory 2Gi \
    --min-replicas 1 --max-replicas 3 \
    --env-vars \
        "API_BASE_URL=https://${API_URL}"

UI_URL=$(az containerapp show \
    --name "$UI_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query properties.configuration.ingress.fqdn \
    -o tsv)

# Step 11: Done
echo ""
echo "=================================================="
echo "  Deployment Complete!"
echo "=================================================="
echo "  UI URL:     https://${UI_URL}"
echo "  API URL:    https://${API_URL}  (docs at /docs)"
echo "  Ollama:     internal-only, at ${OLLAMA_INTERNAL_URL} (not publicly reachable)"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Registry: ${REGISTRY_URL}"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Open https://${UI_URL} in your browser"
echo "  2. Use the Inspector sidebar to load the FinCorp policy PDF (calls POST /ingest on the API)"
echo "  3. Try a query — expect it to be slow (CPU-only Ollama; see note at the top of this script)"
echo "  4. Run data/seed_queries.py locally against https://${API_URL} to populate demo data"
echo ""
echo "To tear everything down: az group delete --name $RESOURCE_GROUP"
