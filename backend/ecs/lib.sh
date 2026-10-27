#!/bin/bash
# ══════════════════════════════════════════════════════════════
# nutrasmart — shared setup for the edge's ECS scripts
# ══════════════════════════════════════════════════════════════
# Sourced by setup.sh, deploy.sh, setup-https.sh and teardown.sh. Loads and exports config.env, then
# offers the checks every script runs first and the SSM step setup.sh runs. Credentials come from
# AWS_PROFILE only, and only for EXPECTED_ACCOUNT_ID. ensure_ssm_parameters is the one function that
# changes AWS, and it only creates parameters that do not exist yet.
# ══════════════════════════════════════════════════════════════

ECS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$ECS_DIR/../.." && pwd)"
HELPERS="$ECS_DIR/deploy_helpers.py"

set -a
# shellcheck source=config.env
source "$ECS_DIR/config.env"
set +a

die() {
    echo "ERROR: $*" >&2
    exit 1
}

# Stop unless AWS_PROFILE is set and resolves to EXPECTED_ACCOUNT_ID; export that as AWS_ACCOUNT_ID.
require_aws_identity() {
    [ -n "${AWS_PROFILE:-}" ] || die "Set AWS_PROFILE to the profile for account $EXPECTED_ACCOUNT_ID."
    local account
    account=$(aws sts get-caller-identity --query Account --output text) \
        || die "AWS_PROFILE=$AWS_PROFILE has no valid credentials."
    [ "$account" = "$EXPECTED_ACCOUNT_ID" ] \
        || die "AWS_PROFILE=$AWS_PROFILE is account $account, not $EXPECTED_ACCOUNT_ID."
    export AWS_ACCOUNT_ID="$account"
    echo "==> Account $AWS_ACCOUNT_ID (profile $AWS_PROFILE), region $AWS_REGION"
}

# Load resources.env (setup.sh writes it) and stop unless it describes this account, project and region.
require_resources() {
    [ -f "$ECS_DIR/resources.env" ] || die "$ECS_DIR/resources.env not found. setup.sh writes it."
    local project="$PROJECT" region="$AWS_REGION"
    # shellcheck source=/dev/null
    source "$ECS_DIR/resources.env"
    [ "$AWS_ACCOUNT_ID" = "$EXPECTED_ACCOUNT_ID" ] \
        || die "resources.env is for account $AWS_ACCOUNT_ID, not $EXPECTED_ACCOUNT_ID."
    [ "$PROJECT" = "$project" ] && [ "$AWS_REGION" = "$region" ] \
        || die "resources.env is for $PROJECT in $AWS_REGION; config.env says $project in $region."
}

# Print a template from this directory with its <NAME> placeholders filled from the environment.
render() {
    python3 "$HELPERS" render "$ECS_DIR/$1"
}

# Export AGENT_ARN_US/IN/CA/EU from the AgentCore projects' deployed-state.json files.
export_runtime_arns() {
    local code arn
    for code in us in ca eu; do
        arn=$(python3 "$HELPERS" runtime-arn "$code")
        export "AGENT_ARN_$(echo "$code" | tr '[:lower:]' '[:upper:]')=$arn"
    done
}

# Create every SSM parameter task-definition.json reads that does not exist yet. An existing parameter
# is never overwritten, so a rerun keeps the live origin secret and runtime ARNs. Needs export_runtime_arns.
ensure_ssm_parameters() {
    local names name path count arn_var
    names=$(python3 "$HELPERS" ssm-names)
    for name in $names; do
        path="/${PROJECT}/${name}"
        count=$(aws ssm describe-parameters --region "$AWS_REGION" \
            --parameter-filters "Key=Name,Option=Equals,Values=$path" \
            --query 'length(Parameters)' --output text)
        if [ "$count" != "0" ]; then
            echo "    $path exists; left unchanged"
            continue
        fi
        case "$name" in
            google-client-id)
                [ -n "$GOOGLE_CLIENT_ID" ] || die "Set GOOGLE_CLIENT_ID in config.env to create $path."
                aws ssm put-parameter --region "$AWS_REGION" --name "$path" --type String \
                    --value "$GOOGLE_CLIENT_ID" > /dev/null
                ;;
            cf-origin-secret)
                # Generated and piped in here, so the value is never in argv, a file or the output.
                python3 -c 'import json, secrets, sys
print(json.dumps({"Name": sys.argv[1], "Type": "SecureString", "Value": secrets.token_hex(32)}))' "$path" \
                    | aws ssm put-parameter --region "$AWS_REGION" --cli-input-json file:///dev/stdin > /dev/null
                ;;
            agent-arn-*)
                arn_var="AGENT_ARN_$(echo "${name#agent-arn-}" | tr '[:lower:]' '[:upper:]')"
                [ -n "${!arn_var:-}" ] || die "$arn_var is not set; run export_runtime_arns first."
                aws ssm put-parameter --region "$AWS_REGION" --name "$path" --type String \
                    --value "${!arn_var}" > /dev/null
                ;;
            *)
                die "lib.sh does not know how to create $path."
                ;;
        esac
        echo "    $path created"
    done
}
