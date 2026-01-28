#!/usr/bin/env python3
"""
LEGO Factory v3 - Secret Generation Script
==========================================
Generate production-ready secrets for deployment.

Usage:
    python scripts/generate_secrets.py
    python scripts/generate_secrets.py --env-file .env.production
    python scripts/generate_secrets.py --format docker
"""

import secrets
import argparse
import sys
from typing import Dict


def generate_secrets() -> Dict[str, str]:
    """Generate all required secrets for production deployment."""
    return {
        'SECRET_KEY': secrets.token_urlsafe(32),
        'JWT_SECRET_KEY': secrets.token_urlsafe(32),
        'POSTGRES_PASSWORD': secrets.token_urlsafe(24),
        'REDIS_PASSWORD': secrets.token_urlsafe(24),
        'MQTT_PASSWORD': secrets.token_urlsafe(24),
    }


def format_env(secrets_dict: Dict[str, str]) -> str:
    """Format secrets as .env file content."""
    lines = [
        "# Generated secrets for LEGO Factory v3",
        "# WARNING: Keep these values secure and never commit to version control!",
        "",
    ]
    for key, value in secrets_dict.items():
        lines.append(f"{key}={value}")
    return "\n".join(lines)


def format_docker(secrets_dict: Dict[str, str]) -> str:
    """Format secrets for docker-compose environment section."""
    lines = [
        "# Docker Compose environment variables",
        "# Add these to your docker-compose.yml environment section",
        "",
        "environment:",
    ]
    for key, value in secrets_dict.items():
        lines.append(f"  - {key}={value}")
    return "\n".join(lines)


def format_kubernetes(secrets_dict: Dict[str, str]) -> str:
    """Format secrets as Kubernetes secret manifest."""
    import base64

    encoded = {k: base64.b64encode(v.encode()).decode() for k, v in secrets_dict.items()}

    lines = [
        "# Kubernetes Secret manifest for LEGO Factory v3",
        "apiVersion: v1",
        "kind: Secret",
        "metadata:",
        "  name: lego-factory-secrets",
        "  namespace: lego-factory",
        "type: Opaque",
        "data:",
    ]
    for key, value in encoded.items():
        lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def format_shell(secrets_dict: Dict[str, str]) -> str:
    """Format secrets as shell export commands."""
    lines = [
        "#!/bin/bash",
        "# Export secrets for LEGO Factory v3",
        "# Source this file: source secrets.sh",
        "",
    ]
    for key, value in secrets_dict.items():
        lines.append(f'export {key}="{value}"')
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate production secrets for LEGO Factory v3"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["env", "docker", "kubernetes", "shell"],
        default="env",
        help="Output format (default: env)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file (default: stdout)"
    )

    args = parser.parse_args()

    # Generate secrets
    secrets_dict = generate_secrets()

    # Format output
    formatters = {
        "env": format_env,
        "docker": format_docker,
        "kubernetes": format_kubernetes,
        "shell": format_shell,
    }

    output = formatters[args.format](secrets_dict)

    # Write output
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
            f.write("\n")
        print(f"Secrets written to {args.output}", file=sys.stderr)
    else:
        print(output)

    # Print security reminder
    print("\n" + "=" * 60, file=sys.stderr)
    print("SECURITY REMINDER:", file=sys.stderr)
    print("- Store these secrets securely (e.g., secrets manager)", file=sys.stderr)
    print("- Never commit secrets to version control", file=sys.stderr)
    print("- Rotate secrets periodically", file=sys.stderr)
    print("- Use different secrets for each environment", file=sys.stderr)
    print("=" * 60, file=sys.stderr)


if __name__ == "__main__":
    main()
