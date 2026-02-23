# LegoMCP AWS Infrastructure Outputs
# PhD-Level Manufacturing Platform

# =============================================================================
# VPC OUTPUTS
# =============================================================================

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "vpc_cidr_block" {
  description = "VPC CIDR block"
  value       = module.vpc.vpc_cidr_block
}

output "private_subnets" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnets
}

output "public_subnets" {
  description = "Public subnet IDs"
  value       = module.vpc.public_subnets
}

# =============================================================================
# EKS OUTPUTS
# =============================================================================

output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "cluster_security_group_id" {
  description = "EKS cluster security group ID"
  value       = module.eks.cluster_security_group_id
}

output "cluster_oidc_issuer_url" {
  description = "OIDC issuer URL for IRSA"
  value       = module.eks.cluster_oidc_issuer_url
}

output "cluster_certificate_authority_data" {
  description = "EKS cluster CA certificate"
  value       = module.eks.cluster_certificate_authority_data
  sensitive   = true
}

output "configure_kubectl" {
  description = "Command to configure kubectl"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

# =============================================================================
# RDS OUTPUTS
# =============================================================================

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = module.rds.db_instance_endpoint
}

output "rds_port" {
  description = "RDS PostgreSQL port"
  value       = module.rds.db_instance_port
}

output "rds_database_name" {
  description = "RDS database name"
  value       = module.rds.db_instance_name
}

output "rds_username" {
  description = "RDS master username"
  value       = module.rds.db_instance_username
  sensitive   = true
}

# =============================================================================
# ELASTICACHE OUTPUTS
# =============================================================================

output "redis_endpoint" {
  description = "ElastiCache Redis primary endpoint"
  value       = aws_elasticache_replication_group.legomcp.primary_endpoint_address
}

output "redis_port" {
  description = "ElastiCache Redis port"
  value       = 6379
}

output "redis_reader_endpoint" {
  description = "ElastiCache Redis reader endpoint"
  value       = aws_elasticache_replication_group.legomcp.reader_endpoint_address
}

# =============================================================================
# S3 OUTPUTS
# =============================================================================

output "s3_bucket_name" {
  description = "S3 bucket name"
  value       = aws_s3_bucket.legomcp.id
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.legomcp.arn
}

output "s3_bucket_domain_name" {
  description = "S3 bucket domain name"
  value       = aws_s3_bucket.legomcp.bucket_domain_name
}

# =============================================================================
# SECRETS MANAGER OUTPUTS
# =============================================================================

output "secrets_manager_arn" {
  description = "Secrets Manager secret ARN"
  value       = aws_secretsmanager_secret.legomcp.arn
}

output "secrets_manager_name" {
  description = "Secrets Manager secret name"
  value       = aws_secretsmanager_secret.legomcp.name
}

# =============================================================================
# KMS OUTPUTS
# =============================================================================

output "kms_key_id" {
  description = "KMS key ID"
  value       = aws_kms_key.legomcp.key_id
}

output "kms_key_arn" {
  description = "KMS key ARN"
  value       = aws_kms_key.legomcp.arn
}

# =============================================================================
# IRSA OUTPUTS
# =============================================================================

output "external_secrets_role_arn" {
  description = "IAM role ARN for External Secrets"
  value       = module.external_secrets_irsa.iam_role_arn
}

# =============================================================================
# HELM VALUES
# =============================================================================

output "helm_values" {
  description = "Helm values for LegoMCP deployment"
  value = {
    externalPostgresql = {
      host     = module.rds.db_instance_address
      port     = module.rds.db_instance_port
      database = module.rds.db_instance_name
      username = module.rds.db_instance_username
    }
    externalRedis = {
      host = aws_elasticache_replication_group.legomcp.primary_endpoint_address
      port = 6379
    }
    secrets = {
      externalSecrets = {
        enabled = true
        secretStore = {
          kind = "ClusterSecretStore"
          name = "aws-secrets-manager"
        }
      }
    }
    backup = {
      storage = {
        type   = "s3"
        bucket = aws_s3_bucket.legomcp.id
        region = var.aws_region
      }
    }
  }
  sensitive = true
}
