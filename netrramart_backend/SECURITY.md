# Neutramart Backend — Security Overview

## Network Security

- Fargate tasks run in **private subnets** — no direct internet access
- ALB in **public subnets** is the only entry point
- **Security groups**: ALB allows only port 80 inbound; Fargate allows only port 8000 from the ALB security group — nothing else

## Credential Security

- **Zero hardcoded AWS keys** — boto3 uses the IAM Task Role automatically on Fargate
- Frontend uses **presigned URLs** for S3 uploads — never sees AWS credentials
- Google Client ID stored in **SSM Parameter Store** (encrypted)

## Container Security

- Runs as **non-root user** (`appuser`)
- **Multi-stage Docker build** (smaller attack surface)
- ECR **scans images for vulnerabilities** on every push
- **Health checks** at both ALB and container level

## Availability & Resilience

- **Auto-scaling** from 1 to 4 tasks based on CPU (70% target)
- ALB distributes traffic across **multiple AZs**
- **Automatic rollback** if deployment fails
- **NAT Gateway** for secure outbound calls (Google Auth, Bedrock)

## Operational

- **CloudWatch logs** with 30-day retention
- **Git SHA image tags** (immutable, traceable)
- **One-command deploy** (`deploy.sh`) and **teardown** (`teardown.sh`)

All 24 AWS components are documented in `DEPLOYMENT.md` (the "What Gets Created" section) and resource IDs are saved in `ecs/resources.env`.

The only thing missing for full production is **HTTPS** — which requires buying a domain. The steps for adding it are documented in the "Adding HTTPS Later" section of `DEPLOYMENT.md`.
