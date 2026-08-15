# nutrasmart Backend — Production Deployment Guide

This guide walks you through deploying the nutrasmart backend to AWS Fargate with production-grade security.

## Current Deployment

| Item             | Value                                                                 |
| ---------------- | --------------------------------------------------------------------- |
| **AWS Account**  | `209479309679`                                                        |
| **AWS Region**   | `ap-south-1` (Mumbai)                                                 |
| **ALB URL**      | `http://nutrasmart-alb-396784627.ap-south-1.elb.amazonaws.com`        |
| **Health Check** | `http://nutrasmart-alb-396784627.ap-south-1.elb.amazonaws.com/health` |
| **S3 Bucket**    | `sci-neutrasmart-project`                                             |
| **ECR Repo**     | `209479309679.dkr.ecr.ap-south-1.amazonaws.com/nutrasmart-backend`    |
| **ECS Cluster**  | `nutrasmart-cluster`                                                  |
| **AWS Profile**  | `nutrasmart` (configured in `~/.aws/credentials`)                     |

---

## What Gets Created

When you run `setup.sh`, it creates the following AWS infrastructure:

| Resource                            | Purpose                                                                          |
| ----------------------------------- | -------------------------------------------------------------------------------- |
| **VPC** (10.0.0.0/16)               | Isolated network for all resources                                               |
| **2 Public Subnets**                | For the Application Load Balancer (internet-facing)                              |
| **2 Private Subnets**               | For Fargate tasks (not directly accessible from internet)                        |
| **Internet Gateway**                | Lets the ALB receive traffic from the internet                                   |
| **NAT Gateway**                     | Lets Fargate tasks make outbound calls (Google Auth, etc.) without being exposed |
| **Application Load Balancer (ALB)** | Single entry point — receives HTTP requests and forwards to Fargate              |
| **Target Group**                    | Health-checked group of Fargate tasks behind the ALB                             |
| **ALB Security Group**              | Only allows HTTP (port 80) from the internet                                     |
| **Fargate Security Group**          | Only allows port 8000 from the ALB (nothing else)                                |
| **IAM Task Execution Role**         | Lets ECS pull images from ECR, write logs, read SSM parameters                   |
| **IAM Task Role**                   | Lets the running container access S3 and Bedrock (no access keys needed!)        |
| **ECR Repository**                  | Stores Docker images with automatic vulnerability scanning                       |
| **CloudWatch Log Group**            | Stores application logs (30-day retention)                                       |
| **ECS Cluster + Service**           | Runs and manages Fargate tasks                                                   |
| **Auto Scaling**                    | Scales from 1 to 4 tasks based on CPU usage (target: 70%)                        |

---

## Security Architecture

```
Internet
    │
    ▼
┌──────────────────────────┐
│  ALB (Public Subnets)    │  ← Security Group: allows port 80 only
│  Port 80 (HTTP)          │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  Fargate (Private Subs)  │  ← Security Group: allows port 8000 from ALB only
│  Port 8000               │  ← IAM Task Role: S3 + Bedrock (no access keys)
│  Non-root container      │  ← Runs as 'appuser', not root
│  Health checked          │  ← /health endpoint monitored by ALB
└──────────────────────────┘
           │
           ▼
    S3 + Bedrock (via IAM Role)
```

**Key security features:**

- No AWS access keys anywhere — the container uses an IAM Task Role
- Fargate tasks are in private subnets — no direct internet access
- Only the ALB can talk to Fargate (port 8000)
- Container runs as non-root user
- ECR scans images for vulnerabilities on every push
- Google Client ID stored in SSM Parameter Store (encrypted)
- Auto scaling protects against traffic spikes

---

## Security Posture (Production Grade)

### Network Security

| Control                                             | Detail                                                                                                                   |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **Private Subnets**                                 | Fargate tasks run in `subnet-087673417fa19c0d4` and `subnet-0fdba34fbeb75d9b8` — no public IP, no direct internet access |
| **ALB as Single Entry Point**                       | All traffic enters through ALB (`nutrasmart-alb-396784627.ap-south-1.elb.amazonaws.com`) in public subnets               |
| **ALB Security Group** (`sg-030f5e4aaeece8c03`)     | Inbound: port 80 (HTTP) from `0.0.0.0/0` only. Nothing else.                                                             |
| **Fargate Security Group** (`sg-0e8ad19027b912880`) | Inbound: port 8000 from ALB security group only. No SSH, no other ports.                                                 |
| **NAT Gateway**                                     | Fargate makes outbound calls (Google Auth, Bedrock, ECR) through NAT — never exposed to internet                         |
| **VPC Isolation**                                   | Dedicated VPC (`vpc-0afcc773dede2af68`, CIDR `10.0.0.0/16`) — all resources are isolated                                 |

### Credential Security

| Control                     | Detail                                                                                                                    |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **Zero Hardcoded AWS Keys** | No `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` anywhere in code or environment variables                               |
| **IAM Task Role**           | Container uses `nutrasmart-ecs-task-role` — boto3 auto-discovers credentials from ECS task metadata                       |
| **IAM Task Execution Role** | `nutrasmart-ecs-execution-role` — only has permissions to pull ECR images, write CloudWatch logs, and read SSM parameters |
| **Presigned URLs for S3**   | Frontend uploads via time-limited presigned URLs (5 min expiry) — frontend never sees AWS credentials                     |
| **SSM Parameter Store**     | Google Client ID stored as encrypted `SecureString` in SSM — not in source code                                           |
| **Least Privilege**         | Task Role only has access to S3 bucket `sci-neutrasmart-project` and Bedrock — nothing else                               |

### Container Security

| Control                        | Detail                                                                                                |
| ------------------------------ | ----------------------------------------------------------------------------------------------------- |
| **Non-Root User**              | Container runs as `appuser` (UID 1000) — not root                                                     |
| **Multi-Stage Build**          | Dockerfile uses builder stage — only runtime dependencies in final image (smaller attack surface)     |
| **ECR Vulnerability Scanning** | Every image push triggers automatic vulnerability scan                                                |
| **Immutable Image Tags**       | Images tagged with git commit SHA (e.g., `abc1234`) — no mutable `:latest` tag in production          |
| **Health Checks**              | ALB health check (`/health`) + Docker `HEALTHCHECK` — unhealthy containers are replaced automatically |

### Availability & Resilience

| Control                | Detail                                                          |
| ---------------------- | --------------------------------------------------------------- |
| **Auto Scaling**       | 1 to 4 Fargate tasks based on CPU utilization (target: 70%)     |
| **Multi-AZ**           | ALB and subnets span `ap-south-1a` and `ap-south-1b`            |
| **Automatic Rollback** | `deploy.sh` waits for service stability — rolls back on failure |
| **CloudWatch Logs**    | 30-day retention in `/ecs/nutrasmart-backend` log group         |

### What's NOT Covered Yet (Recommended for Full Production)

| Item                               | Status                      | How to Add                                                        |
| ---------------------------------- | --------------------------- | ----------------------------------------------------------------- |
| **HTTPS (TLS)**                    | Not yet — requires a domain | See "Adding HTTPS Later" section below                            |
| **WAF (Web Application Firewall)** | Not yet                     | Attach AWS WAF to ALB for rate limiting, SQL injection protection |
| **Secrets Manager**                | Using SSM (sufficient)      | Migrate to Secrets Manager for automatic key rotation             |
| **VPC Flow Logs**                  | Not yet                     | Enable for network traffic auditing                               |
| **GuardDuty**                      | Not yet                     | Enable for threat detection on the AWS account                    |

---

## Prerequisites

Before you start, make sure you have:

1. **AWS CLI v2** installed and configured

   ```bash
   aws --version          # Should be 2.x.x
   aws sts get-caller-identity  # Should show your account
   ```

2. **Docker** installed and running

   ```bash
   docker --version
   ```

3. **jq** installed (for JSON parsing)

   ```bash
   brew install jq        # macOS
   ```

4. **Your AWS Account ID** — the setup script auto-detects this

5. **Your Google OAuth Client ID** — you'll be prompted during setup
   - This is: `1002409619791-66n3jv66p121t7g0qmasukau0r6tc6i1.apps.googleusercontent.com`

---

## Step 1: Run Setup (One-Time)

This creates all the infrastructure. Takes about 5 minutes (mostly waiting for NAT Gateway).

```bash
cd netrramart_backend/ecs
./setup.sh
```

You'll be prompted for your Google OAuth Client ID. Enter it when asked.

When done, you'll see:

```
══════════════════════════════════════════════
  SETUP COMPLETE
══════════════════════════════════════════════

  ALB URL:  http://nutrasmart-alb-xxxxxxxx.ap-south-1.elb.amazonaws.com
  Health:   http://nutrasmart-alb-xxxxxxxx.ap-south-1.elb.amazonaws.com/health
```

**Save that ALB URL** — you'll need it for the frontend.

A `resources.env` file is created in the `ecs/` folder with all resource IDs. This is used by `deploy.sh` and `teardown.sh`.

---

## Step 2: Deploy

Build the Docker image, push to ECR, and deploy to Fargate:

```bash
cd netrramart_backend/ecs
./deploy.sh
```

This will:

1. Build the Docker image (for linux/amd64)
2. Push it to ECR with a git commit SHA tag
3. Trigger a new ECS deployment
4. Wait for the service to stabilize
5. Auto-rollback if deployment fails

When done:

```
══════════════════════════════════════════════
  DEPLOYMENT SUCCESSFUL
══════════════════════════════════════════════

  Image:  123456789.dkr.ecr.ap-south-1.amazonaws.com/nutrasmart-backend:abc1234
  URL:    http://nutrasmart-alb-xxxxxxxx.ap-south-1.elb.amazonaws.com
  Health: http://nutrasmart-alb-xxxxxxxx.ap-south-1.elb.amazonaws.com/health
```

---

## Step 3: Verify

Test the health endpoint:

```bash
curl http://nutrasmart-alb-396784627.ap-south-1.elb.amazonaws.com/health
# Should return: {"status":"healthy"}
```

---

## Step 4: Update Frontend

Update your frontend to point to the ALB URL.

In `nutrasmart_ui/src/config/api.js`, change the API_URL:

```javascript
export const API_URL = "http://<YOUR_ALB_DNS>";
```

Or better, use an environment variable:

```javascript
export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
```

Then in your `.env.local`:

```
VITE_API_URL=http://nutrasmart-alb-396784627.ap-south-1.elb.amazonaws.com/api
```

---

## Redeploying After Code Changes

Every time you change backend code:

```bash
cd netrramart_backend/ecs
./deploy.sh
```

That's it. The script handles everything — build, push, deploy, verify.

---

## Viewing Logs

```bash
# Tail live logs
aws logs tail /ecs/nutrasmart-backend --region ap-south-1 --profile nutrasmart --follow

# Last 30 minutes
aws logs tail /ecs/nutrasmart-backend --region ap-south-1 --profile nutrasmart --since 30m
```

---

## Checking Service Status

```bash
aws ecs describe-services \
  --cluster nutrasmart-cluster \
  --services nutrasmart-backend-service \
  --region ap-south-1 \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Health:healthCheckGracePeriodSeconds}'
```

---

## Teardown (Delete Everything)

To delete all AWS resources:

```bash
cd netrramart_backend/ecs
./teardown.sh
```

You'll be asked to type `DELETE` to confirm. This removes everything — VPC, ALB, ECS, IAM roles, ECR, logs — all of it.

---

## Adding HTTPS Later

When you're ready to add HTTPS (recommended for production):

### 1. Buy a Domain

- Go to [AWS Route53](https://console.aws.amazon.com/route53/) or any domain registrar (GoDaddy, Namecheap, etc.)
- Example: `nutrasmart.com` or `api.nutrasmart.com`
- A domain is like your address on the internet — instead of users going to `http://nutrasmart-alb-xxxxxxxx.elb.amazonaws.com`, they go to `https://api.nutrasmart.com`

### 2. Get an SSL Certificate (Free from AWS)

```bash
# Request a certificate
aws acm request-certificate \
  --domain-name api.nutrasmart.com \
  --validation-method DNS \
  --region ap-south-1

# You'll get a certificate ARN — save it
```

### 3. Validate the Certificate

- AWS will ask you to add a DNS record to prove you own the domain
- If using Route53, this can be done automatically
- If using another registrar, add the CNAME record they provide

### 4. Add HTTPS Listener to ALB

```bash
# Get your ALB ARN and Target Group ARN from resources.env
source ecs/resources.env

# Add HTTPS listener
aws elbv2 create-listener \
  --load-balancer-arn $ALB_ARN \
  --protocol HTTPS \
  --port 443 \
  --certificates CertificateArn=<YOUR_CERT_ARN> \
  --default-actions Type=forward,TargetGroupArn=$TG_ARN \
  --region ap-south-1

# Update ALB security group to allow 443
aws ec2 authorize-security-group-ingress \
  --group-id $ALB_SG \
  --protocol tcp --port 443 --cidr 0.0.0.0/0 \
  --region ap-south-1

# Redirect HTTP to HTTPS (optional but recommended)
# Delete old HTTP listener and create a redirect
```

### 5. Point Domain to ALB

- In Route53 (or your DNS provider), create an A record (or CNAME) pointing to the ALB DNS

### 6. Update Frontend and CORS

- Change `API_URL` to `https://api.nutrasmart.com`
- Update `ALLOWED_ORIGINS` in the ECS task definition

---

## Estimated Costs

| Resource                        | Approximate Monthly Cost |
| ------------------------------- | ------------------------ |
| NAT Gateway                     | ~$32 + data transfer     |
| ALB                             | ~$16 + data transfer     |
| Fargate (1 task, 0.5 vCPU, 1GB) | ~$15                     |
| ECR (image storage)             | ~$1                      |
| CloudWatch Logs                 | ~$1                      |
| **Total (1 task)**              | **~$65/month**           |

To reduce costs during development:

- Scale down to 0 tasks when not testing: `aws ecs update-service --cluster nutrasmart-cluster --service nutrasmart-backend-service --desired-count 0 --region ap-south-1`
- Scale back up: `aws ecs update-service --cluster nutrasmart-cluster --service nutrasmart-backend-service --desired-count 1 --region ap-south-1`
- Or run `teardown.sh` and re-run `setup.sh` + `deploy.sh` when needed

---

## Troubleshooting

### Service won't start

```bash
# Check ECS events
aws ecs describe-services --cluster nutrasmart-cluster --services nutrasmart-backend-service --region ap-south-1 --query 'services[0].events[:5]'

# Check logs
aws logs tail /ecs/nutrasmart-backend --region ap-south-1 --since 10m
```

### Health check failing

- Make sure `/health` endpoint returns 200
- Check security group rules (Fargate SG must allow 8000 from ALB SG)
- Check target group health: `aws elbv2 describe-target-health --target-group-arn <TG_ARN> --region ap-south-1`

### Container crash loop

- Usually a code error — check CloudWatch logs
- Test locally first: `docker build -t test . && docker run -p 8000:8000 test`

### Permission denied (S3 or Bedrock)

- The IAM Task Role needs the right permissions
- Check: `aws iam get-role-policy --role-name nutrasmart-ecs-task-role --policy-name nutrasmart-s3-bedrock`
