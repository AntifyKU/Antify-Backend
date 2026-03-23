#!/bin/bash

# Configuration
SERVICE_NAME="antify-backend"
REGION="asia-southeast1" # Update to your preferred region

echo "🚀 Deploying $SERVICE_NAME to Google Cloud Run..."

# Build and Push using Cloud Build (No local Docker needed)
gcloud builds submit --tag gcr.io/$(gcloud config get-value project)/$SERVICE_NAME

# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$(gcloud config get-value project)/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars="AI_SERVICE_URL=https://antify-ai-component-un6q7l6uaq-as.a.run.app"

echo "✅ Deployment complete!"
