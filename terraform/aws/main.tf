# LegoMCP AWS Infrastructure
# PhD-Level Manufacturing Platform - Terraform IaC

terraform {
  required_version = ">= 1.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
  }

  backend "s3" {
    bucket         = "legomcp-terraform-state"
    key            = "aws/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "legomcp-terraform-locks"
  }
}

# =============================================================================
# PROVIDERS
# =============================================================================

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "LegoMCP"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    }
  }
}

# =============================================================================
# DATA SOURCES
# =============================================================================

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# =============================================================================
# LOCAL VALUES
# =============================================================================

locals {
  name            = "legomcp-${var.environment}"
  cluster_version = "1.28"

  vpc_cidr = "10.0.0.0/16"
  azs      = slice(data.aws_availability_zones.available.names, 0, 3)

  tags = {
    Project     = "LegoMCP"
    Environment = var.environment
  }
}

# =============================================================================
# VPC MODULE
# =============================================================================

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${local.name}-vpc"
  cidr = local.vpc_cidr

  azs             = local.azs
  private_subnets = [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 4, k)]
  public_subnets  = [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 8, k + 48)]
  intra_subnets   = [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 8, k + 52)]

  enable_nat_gateway   = true
  single_nat_gateway   = var.environment != "prod"
  enable_dns_hostnames = true
  enable_dns_support   = true

  # VPC Flow Logs
  enable_flow_log                      = true
  create_flow_log_cloudwatch_log_group = true
  create_flow_log_cloudwatch_iam_role  = true
  flow_log_max_aggregation_interval    = 60

  # Subnet tags for EKS
  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
  }

  tags = local.tags
}

# =============================================================================
# EKS CLUSTER
# =============================================================================

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = "${local.name}-eks"
  cluster_version = local.cluster_version

  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Cluster addons
  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent              = true
      before_compute           = true
      service_account_role_arn = module.vpc_cni_irsa.iam_role_arn
      configuration_values = jsonencode({
        env = {
          ENABLE_PREFIX_DELEGATION = "true"
          WARM_PREFIX_TARGET       = "1"
        }
      })
    }
    aws-ebs-csi-driver = {
      most_recent              = true
      service_account_role_arn = module.ebs_csi_irsa.iam_role_arn
    }
  }

  # Node groups
  eks_managed_node_groups = {
    # General purpose nodes
    general = {
      name            = "general"
      instance_types  = var.environment == "prod" ? ["m6i.xlarge"] : ["m6i.large"]
      capacity_type   = var.environment == "prod" ? "ON_DEMAND" : "SPOT"
      min_size        = var.environment == "prod" ? 3 : 1
      max_size        = var.environment == "prod" ? 10 : 5
      desired_size    = var.environment == "prod" ? 3 : 2

      labels = {
        workload = "general"
      }

      tags = {
        "k8s.io/cluster-autoscaler/enabled"             = "true"
        "k8s.io/cluster-autoscaler/${local.name}-eks"   = "owned"
      }
    }

    # GPU nodes for ML workloads
    gpu = {
      name            = "gpu"
      instance_types  = ["g4dn.xlarge"]
      capacity_type   = "ON_DEMAND"
      min_size        = 0
      max_size        = var.environment == "prod" ? 4 : 2
      desired_size    = var.environment == "prod" ? 1 : 0

      ami_type = "AL2_x86_64_GPU"

      labels = {
        workload    = "ml"
        accelerator = "nvidia-gpu"
      }

      taints = [{
        key    = "nvidia.com/gpu"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]

      tags = {
        "k8s.io/cluster-autoscaler/enabled"             = "true"
        "k8s.io/cluster-autoscaler/${local.name}-eks"   = "owned"
      }
    }
  }

  # OIDC provider for IRSA
  enable_irsa = true

  # Cluster security group rules
  cluster_security_group_additional_rules = {
    ingress_nodes_ephemeral_ports_tcp = {
      description                = "Nodes to cluster API"
      protocol                   = "tcp"
      from_port                  = 1025
      to_port                    = 65535
      type                       = "ingress"
      source_node_security_group = true
    }
  }

  # Node security group rules
  node_security_group_additional_rules = {
    ingress_self_all = {
      description = "Node to node all ports/protocols"
      protocol    = "-1"
      from_port   = 0
      to_port     = 0
      type        = "ingress"
      self        = true
    }
  }

  tags = local.tags
}

# =============================================================================
# IRSA ROLES
# =============================================================================

module "vpc_cni_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name             = "${local.name}-vpc-cni"
  attach_vpc_cni_policy = true
  vpc_cni_enable_ipv4   = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:aws-node"]
    }
  }

  tags = local.tags
}

module "ebs_csi_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name             = "${local.name}-ebs-csi"
  attach_ebs_csi_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"]
    }
  }

  tags = local.tags
}

module "external_secrets_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name = "${local.name}-external-secrets"

  attach_external_secrets_policy        = true
  external_secrets_secrets_manager_arns = [aws_secretsmanager_secret.legomcp.arn]

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["legomcp:external-secrets"]
    }
  }

  tags = local.tags
}

# =============================================================================
# RDS POSTGRESQL
# =============================================================================

module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"

  identifier = "${local.name}-postgres"

  engine               = "postgres"
  engine_version       = "15.4"
  family               = "postgres15"
  major_engine_version = "15"
  instance_class       = var.environment == "prod" ? "db.r6g.large" : "db.t4g.medium"

  allocated_storage     = var.environment == "prod" ? 100 : 20
  max_allocated_storage = var.environment == "prod" ? 500 : 100

  db_name  = "legomcp"
  username = "lego"
  port     = 5432

  # Multi-AZ for production
  multi_az = var.environment == "prod"

  # Subnet group
  db_subnet_group_name   = module.vpc.database_subnet_group_name
  vpc_security_group_ids = [module.rds_security_group.security_group_id]

  # Backup
  backup_retention_period = var.environment == "prod" ? 30 : 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  # Encryption
  storage_encrypted = true
  kms_key_id        = aws_kms_key.legomcp.arn

  # Performance Insights
  performance_insights_enabled          = true
  performance_insights_retention_period = 7

  # Enhanced monitoring
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn

  # Parameters
  parameters = [
    {
      name  = "log_statement"
      value = "all"
    },
    {
      name  = "log_min_duration_statement"
      value = "1000"
    }
  ]

  tags = local.tags
}

module "rds_security_group" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "~> 5.0"

  name        = "${local.name}-rds"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = module.vpc.vpc_id

  ingress_with_source_security_group_id = [
    {
      from_port                = 5432
      to_port                  = 5432
      protocol                 = "tcp"
      description              = "PostgreSQL from EKS"
      source_security_group_id = module.eks.node_security_group_id
    }
  ]

  tags = local.tags
}

# =============================================================================
# ELASTICACHE REDIS
# =============================================================================

resource "aws_elasticache_subnet_group" "legomcp" {
  name       = "${local.name}-redis"
  subnet_ids = module.vpc.private_subnets

  tags = local.tags
}

resource "aws_elasticache_replication_group" "legomcp" {
  replication_group_id       = "${local.name}-redis"
  description                = "LegoMCP Redis cluster"
  node_type                  = var.environment == "prod" ? "cache.r6g.large" : "cache.t4g.medium"
  num_cache_clusters         = var.environment == "prod" ? 2 : 1
  automatic_failover_enabled = var.environment == "prod"
  multi_az_enabled           = var.environment == "prod"

  engine               = "redis"
  engine_version       = "7.0"
  parameter_group_name = "default.redis7"
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.legomcp.name
  security_group_ids = [module.redis_security_group.security_group_id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = random_password.redis_auth.result

  snapshot_retention_limit = var.environment == "prod" ? 7 : 1
  snapshot_window          = "05:00-06:00"

  tags = local.tags
}

module "redis_security_group" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "~> 5.0"

  name        = "${local.name}-redis"
  description = "Security group for ElastiCache Redis"
  vpc_id      = module.vpc.vpc_id

  ingress_with_source_security_group_id = [
    {
      from_port                = 6379
      to_port                  = 6379
      protocol                 = "tcp"
      description              = "Redis from EKS"
      source_security_group_id = module.eks.node_security_group_id
    }
  ]

  tags = local.tags
}

# =============================================================================
# S3 BUCKETS
# =============================================================================

resource "aws_s3_bucket" "legomcp" {
  bucket = "${local.name}-storage-${data.aws_caller_identity.current.account_id}"

  tags = local.tags
}

resource "aws_s3_bucket_versioning" "legomcp" {
  bucket = aws_s3_bucket.legomcp.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "legomcp" {
  bucket = aws_s3_bucket.legomcp.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.legomcp.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "legomcp" {
  bucket = aws_s3_bucket.legomcp.id

  rule {
    id     = "backup-retention"
    status = "Enabled"

    filter {
      prefix = "backups/"
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }
  }

  rule {
    id     = "models-retention"
    status = "Enabled"

    filter {
      prefix = "models/"
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# =============================================================================
# SECRETS MANAGER
# =============================================================================

resource "aws_secretsmanager_secret" "legomcp" {
  name        = "${local.name}/secrets"
  description = "LegoMCP application secrets"
  kms_key_id  = aws_kms_key.legomcp.arn

  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "legomcp" {
  secret_id = aws_secretsmanager_secret.legomcp.id
  secret_string = jsonencode({
    database_url       = "postgresql://${module.rds.db_instance_username}:${random_password.db_password.result}@${module.rds.db_instance_endpoint}/${module.rds.db_instance_name}"
    redis_url          = "rediss://:${random_password.redis_auth.result}@${aws_elasticache_replication_group.legomcp.primary_endpoint_address}:6379"
    flask_secret_key   = random_password.flask_secret.result
    jwt_secret_key     = random_password.jwt_secret.result
  })
}

# =============================================================================
# KMS
# =============================================================================

resource "aws_kms_key" "legomcp" {
  description             = "LegoMCP encryption key"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = local.tags
}

resource "aws_kms_alias" "legomcp" {
  name          = "alias/${local.name}"
  target_key_id = aws_kms_key.legomcp.key_id
}

# =============================================================================
# RANDOM PASSWORDS
# =============================================================================

resource "random_password" "db_password" {
  length  = 32
  special = false
}

resource "random_password" "redis_auth" {
  length  = 32
  special = false
}

resource "random_password" "flask_secret" {
  length  = 64
  special = true
}

resource "random_password" "jwt_secret" {
  length  = 64
  special = true
}

# =============================================================================
# IAM ROLES
# =============================================================================

resource "aws_iam_role" "rds_monitoring" {
  name = "${local.name}-rds-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  managed_policy_arns = [
    "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
  ]

  tags = local.tags
}
