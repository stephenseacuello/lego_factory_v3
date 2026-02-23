# LegoMCP AWS Infrastructure Variables
# PhD-Level Manufacturing Platform

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "legomcp"
}

# VPC Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway for private subnets"
  type        = bool
  default     = true
}

variable "single_nat_gateway" {
  description = "Use single NAT Gateway (cost savings for non-prod)"
  type        = bool
  default     = true
}

# EKS Configuration
variable "cluster_version" {
  description = "Kubernetes version for EKS"
  type        = string
  default     = "1.28"
}

variable "node_instance_types" {
  description = "Instance types for general purpose nodes"
  type        = list(string)
  default     = ["m6i.large"]
}

variable "gpu_instance_types" {
  description = "Instance types for GPU nodes"
  type        = list(string)
  default     = ["g4dn.xlarge"]
}

variable "min_nodes" {
  description = "Minimum number of general purpose nodes"
  type        = number
  default     = 1
}

variable "max_nodes" {
  description = "Maximum number of general purpose nodes"
  type        = number
  default     = 10
}

variable "desired_nodes" {
  description = "Desired number of general purpose nodes"
  type        = number
  default     = 2
}

variable "min_gpu_nodes" {
  description = "Minimum number of GPU nodes"
  type        = number
  default     = 0
}

variable "max_gpu_nodes" {
  description = "Maximum number of GPU nodes"
  type        = number
  default     = 4
}

# RDS Configuration
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.medium"
}

variable "db_allocated_storage" {
  description = "Allocated storage for RDS in GB"
  type        = number
  default     = 20
}

variable "db_max_allocated_storage" {
  description = "Maximum allocated storage for RDS autoscaling in GB"
  type        = number
  default     = 100
}

variable "db_backup_retention_period" {
  description = "Number of days to retain backups"
  type        = number
  default     = 7
}

variable "db_multi_az" {
  description = "Enable Multi-AZ for RDS"
  type        = bool
  default     = false
}

# ElastiCache Configuration
variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.t4g.medium"
}

variable "redis_num_cache_clusters" {
  description = "Number of cache clusters for Redis"
  type        = number
  default     = 1
}

# S3 Configuration
variable "enable_s3_versioning" {
  description = "Enable versioning for S3 bucket"
  type        = bool
  default     = true
}

variable "backup_retention_days" {
  description = "Number of days to retain backups in S3"
  type        = number
  default     = 365
}

# Monitoring Configuration
variable "enable_cloudwatch_logs" {
  description = "Enable CloudWatch Logs for EKS"
  type        = bool
  default     = true
}

variable "cloudwatch_log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

# Tags
variable "additional_tags" {
  description = "Additional tags for all resources"
  type        = map(string)
  default     = {}
}
