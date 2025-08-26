# Worker API Key Setup Guide

This guide explains how to create and configure API keys for worker authentication.

## Overview

Workers authenticate with the API using API keys instead of pre-configured secrets. This provides better security and allows administrators to manage worker access through the web dashboard.

## Steps to Set Up Worker Authentication

### 1. Create API Key Through Dashboard

1. Log in to the web dashboard
2. Navigate to **API Keys** in the sidebar
3. Click **Create API Key**
4. Fill in the details:
   - **Name**: Descriptive name (e.g., "Production Worker 01", "Development Worker")
   - **Role**: Select "worker"
   - **Expiration Date**: Optional, leave blank for non-expiring keys
5. Click **Create API Key**
6. **Important**: Copy the generated API key immediately - it will only be shown once!

### 2. Configure Worker with API Key

Update your worker's environment configuration:

```bash
# .env file or environment variables
WORKER_API_KEY=<your-generated-api-key>
TENANT_ID=<your-tenant-id>
SITE_ID=<your-site-id>
```

### 3. Start Worker

The worker will now authenticate using the API key:

```bash
cd apps/worker
python -m app.main
```

## API Key Management

### View API Keys
- Navigate to **API Keys** in the dashboard
- View all keys with their status, last usage, and expiration

### Update API Keys
- Edit key names, toggle active/inactive status, or update expiration dates
- Deactivated keys will immediately stop working

### Delete API Keys
- Remove keys that are no longer needed
- Deleted keys cannot be recovered

### Security Best Practices

1. **Use descriptive names** for API keys to identify their purpose
2. **Set expiration dates** for temporary or testing keys
3. **Regularly rotate keys** by creating new ones and deactivating old ones
4. **Monitor key usage** through the "Last Used" column
5. **Immediately deactivate** compromised keys
6. **Use different keys** for different workers/environments

## Troubleshooting

### 401 Authentication Errors

If you're getting 401 errors:

1. **Check API key**: Ensure the `WORKER_API_KEY` environment variable contains a valid key
2. **Check key status**: Verify the key is active in the dashboard
3. **Check expiration**: Ensure the key hasn't expired
4. **Check tenant ID**: Ensure `TENANT_ID` matches the tenant the API key belongs to

### Worker Not Connecting

1. **Check API URL**: Ensure `API_URL` points to the correct API endpoint
2. **Check network**: Verify the worker can reach the API server
3. **Check logs**: Review worker logs for detailed error messages

## Migration from Pre-configured Keys

If you're currently using pre-configured secret keys:

1. Create a new API key through the dashboard
2. Update your worker's `WORKER_API_KEY` environment variable
3. Restart the worker
4. Remove any hardcoded secrets from configuration files

## Example Configuration

```bash
# Worker Environment Configuration
API_URL=http://your-api-server:8080
WORKER_API_KEY=abcd1234efgh5678ijkl9012mnop3456qrst7890uvwx  # From dashboard
TENANT_ID=t-your-tenant
SITE_ID=s-1

# Worker Settings
USE_ENHANCED_WORKER=true
WORKER_ID=worker-001
WORKER_HTTP_PORT=8090
DETECTOR_TYPE=yunet
EMBEDDER_TYPE=insightface
WORKER_FPS=5
```

## API Endpoints

The worker uses these authentication endpoints:

- `POST /v1/auth/token` - Exchange API key for JWT token
- All other API calls use the JWT token in Authorization header

The authentication flow:
1. Worker sends API key to `/v1/auth/token`
2. API validates key and returns JWT token
3. Worker uses JWT token for all subsequent API calls
4. JWT tokens expire and are automatically refreshed as needed