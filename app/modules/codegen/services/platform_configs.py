"""Platform-specific deployment configuration generators.

Each generator takes a solution context dict and returns a dict of
{filepath: content} for that platform's deployment configs.

Supported platforms:
- docker-compose: Docker Compose + Dockerfile
- kubernetes: K8s manifests (Deployment, Service, Secret, Ingress, ConfigMap)
- aws: Terraform for ECS + RDS + ALB
- azure: Terraform for App Service + SQL + Front Door
- gcp: Terraform for Cloud Run + Cloud SQL
"""
import logging

logger = logging.getLogger(__name__)


def generate_docker_compose(ctx: dict) -> dict:
    """Generate Docker Compose deployment files."""
    solution_id = ctx.get("solution_id", 0)
    name = ctx.get("solution_name", f"solution-{solution_id}").lower().replace(" ", "-")
    port = ctx.get("port", 8000)

    files = {}

    files["Dockerfile"] = f"""FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE {port}
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "{port}"]
"""

    files["docker-compose.yml"] = f"""version: '3.8'
services:
  app:
    build: .
    container_name: {name}-app
    ports:
      - "{port}:{port}"
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{port}/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:16-alpine
    container_name: {name}-db
    environment:
      POSTGRES_USER: ${{POSTGRES_USER:-archie}}
      POSTGRES_PASSWORD: ${{POSTGRES_PASSWORD:-changeme}}
      POSTGRES_DB: {name.replace('-', '_')}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U archie"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: {name}-redis

volumes:
  pgdata:
"""

    files["DEPLOY.md"] = f"""# Deployment: Docker Compose

## Prerequisites
- Docker and Docker Compose installed

## Quick Start
```bash
cp .env.example .env
# Edit .env with your values
docker-compose up -d
```

## Verify
```bash
curl http://localhost:{port}/health
```

## Logs
```bash
docker-compose logs -f app
```
"""

    return files


def generate_kubernetes(ctx: dict) -> dict:
    """Generate Kubernetes deployment manifests."""
    solution_id = ctx.get("solution_id", 0)
    name = ctx.get("solution_name", f"solution-{solution_id}").lower().replace(" ", "-")
    port = ctx.get("port", 8000)
    env_vars = ctx.get("env_vars", [])

    files = {}

    files["k8s/deployment.yaml"] = f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
  labels:
    app: {name}
spec:
  replicas: 2
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
    spec:
      containers:
      - name: app
        image: {name}:latest
        ports:
        - containerPort: {port}
        envFrom:
        - secretRef:
            name: {name}-env
        readinessProbe:
          httpGet:
            path: /health
            port: {port}
          initialDelaySeconds: 10
          periodSeconds: 15
        livenessProbe:
          httpGet:
            path: /health
            port: {port}
          initialDelaySeconds: 30
          periodSeconds: 30
        resources:
          requests:
            cpu: 250m
            memory: 256Mi
          limits:
            cpu: "1"
            memory: 512Mi
"""

    files["k8s/service.yaml"] = f"""apiVersion: v1
kind: Service
metadata:
  name: {name}
spec:
  type: ClusterIP
  ports:
  - port: 80
    targetPort: {port}
    protocol: TCP
  selector:
    app: {name}
"""

    env_data = "\n".join(f"  {v}: REPLACE_ME" for v in env_vars)
    files["k8s/secret.yaml"] = f"""apiVersion: v1
kind: Secret
metadata:
  name: {name}-env
type: Opaque
stringData:
{env_data}
"""

    files["k8s/ingress.yaml"] = f"""apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {name}
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  rules:
  - host: {name}.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: {name}
            port:
              number: 80
  tls:
  - hosts:
    - {name}.example.com
    secretName: {name}-tls
"""

    files["k8s/configmap.yaml"] = f"""apiVersion: v1
kind: ConfigMap
metadata:
  name: {name}-config
data:
  APP_NAME: {name}
  LOG_LEVEL: info
"""

    files["DEPLOY.md"] = f"""# Deployment: Kubernetes

## Prerequisites
- kubectl configured for your cluster
- Container registry access

## Steps
```bash
# Build and push image
docker build -t your-registry/{name}:latest .
docker push your-registry/{name}:latest

# Update image in deployment.yaml, then:
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

## Verify
```bash
kubectl get pods -l app={name}
kubectl logs -l app={name} --tail=50
```
"""

    return files


def generate_aws(ctx: dict) -> dict:
    """Generate Terraform configs for AWS ECS + RDS + ALB."""
    solution_id = ctx.get("solution_id", 0)
    name = ctx.get("solution_name", f"solution-{solution_id}").lower().replace(" ", "-")
    port = ctx.get("port", 8000)
    tf_name = name.replace("-", "_")

    files = {}

    files["terraform/main.tf"] = f"""terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region = var.aws_region
}}

# -- VPC ----------------------------------------------------------------------

module "vpc" {{
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "{name}-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${{var.aws_region}}a", "${{var.aws_region}}b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true
}}

# -- RDS ----------------------------------------------------------------------

resource "aws_db_instance" "{tf_name}_rds" {{
  identifier        = "{name}-db"
  engine            = "postgres"
  engine_version    = "16"
  instance_class    = var.db_instance_class
  allocated_storage = 20

  db_name  = "{tf_name}"
  username = "archie"
  password = var.db_password

  vpc_security_group_ids = [aws_security_group.db.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name

  skip_final_snapshot = true
}}

resource "aws_db_subnet_group" "main" {{
  name       = "{name}-db-subnet"
  subnet_ids = module.vpc.private_subnets
}}

resource "aws_security_group" "db" {{
  name   = "{name}-db-sg"
  vpc_id = module.vpc.vpc_id

  ingress {{
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }}
}}

# -- ECS ----------------------------------------------------------------------

resource "aws_ecs_cluster" "main" {{
  name = "{name}-cluster"
}}

resource "aws_ecs_task_definition" "app" {{
  family                   = "{name}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn

  container_definitions = jsonencode([{{
    name      = "app"
    image     = "${{var.ecr_repository_url}}:latest"
    portMappings = [{{ containerPort = {port}, protocol = "tcp" }}]
    environment = [
      {{ name = "DATABASE_URL", value = "postgresql://archie:${{var.db_password}}@${{aws_db_instance.{tf_name}_rds.endpoint}}/{tf_name}" }}
    ]
    logConfiguration = {{
      logDriver = "awslogs"
      options = {{
        "awslogs-group"         = "/ecs/{name}"
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }}
    }}
  }}])
}}

resource "aws_ecs_service" "app" {{
  name            = "{name}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {{
    subnets         = module.vpc.private_subnets
    security_groups = [aws_security_group.app.id]
  }}

  load_balancer {{
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = {port}
  }}
}}

resource "aws_security_group" "app" {{
  name   = "{name}-app-sg"
  vpc_id = module.vpc.vpc_id

  ingress {{
    from_port       = {port}
    to_port         = {port}
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }}

  egress {{
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }}
}}

# -- ALB ----------------------------------------------------------------------

resource "aws_lb" "main" {{
  name               = "{name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets
}}

resource "aws_lb_target_group" "app" {{
  name        = "{name}-tg"
  port        = {port}
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "ip"

  health_check {{
    path = "/health"
  }}
}}

resource "aws_lb_listener" "https" {{
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {{
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }}
}}

resource "aws_security_group" "alb" {{
  name   = "{name}-alb-sg"
  vpc_id = module.vpc.vpc_id

  ingress {{
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }}

  egress {{
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }}
}}

resource "aws_iam_role" "ecs_execution" {{
  name = "{name}-ecs-execution"
  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{ Action = "sts:AssumeRole", Effect = "Allow", Principal = {{ Service = "ecs-tasks.amazonaws.com" }} }}]
  }})
}}

resource "aws_iam_role_policy_attachment" "ecs_execution" {{
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}}
"""

    files["terraform/variables.tf"] = f"""variable "aws_region" {{
  default = "eu-west-1"
}}

variable "db_password" {{
  sensitive = true
}}

variable "db_instance_class" {{
  default = "db.t3.micro"
}}

variable "ecr_repository_url" {{
  description = "ECR repository URL for the app image"
}}

variable "certificate_arn" {{
  description = "ACM certificate ARN for HTTPS"
}}
"""

    files["terraform/outputs.tf"] = f"""output "alb_dns_name" {{
  value = aws_lb.main.dns_name
}}

output "rds_endpoint" {{
  value = aws_db_instance.{tf_name}_rds.endpoint
}}

output "ecs_cluster_name" {{
  value = aws_ecs_cluster.main.name
}}
"""

    files["DEPLOY.md"] = f"""# Deployment: AWS (ECS + RDS + ALB)

## Prerequisites
- AWS CLI configured
- Terraform >= 1.5
- ECR repository created
- ACM certificate for your domain

## Steps
```bash
# Build and push Docker image to ECR
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.eu-west-1.amazonaws.com
docker build -t {name} .
docker tag {name}:latest <account>.dkr.ecr.eu-west-1.amazonaws.com/{name}:latest
docker push <account>.dkr.ecr.eu-west-1.amazonaws.com/{name}:latest

# Deploy infrastructure
cd terraform
terraform init
terraform plan -var="db_password=YOUR_SECURE_PASSWORD" -var="ecr_repository_url=<account>.dkr.ecr.eu-west-1.amazonaws.com/{name}" -var="certificate_arn=arn:aws:acm:..."
terraform apply
```
"""

    return files


def generate_azure(ctx: dict) -> dict:
    """Generate Terraform configs for Azure App Service + SQL + Front Door."""
    solution_id = ctx.get("solution_id", 0)
    name = ctx.get("solution_name", f"solution-{solution_id}").lower().replace(" ", "-")
    tf_name = name.replace("-", "_")

    files = {}

    files["terraform/main.tf"] = f"""terraform {{
  required_providers {{
    azurerm = {{
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }}
  }}
}}

provider "azurerm" {{
  features {{}}
}}

resource "azurerm_resource_group" "main" {{
  name     = "{name}-rg"
  location = var.location
}}

# -- App Service ---------------------------------------------------------------

resource "azurerm_service_plan" "main" {{
  name                = "{name}-plan"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = "B1"
}}

resource "azurerm_linux_web_app" "main" {{
  name                = "{name}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  service_plan_id     = azurerm_service_plan.main.id

  site_config {{
    application_stack {{
      docker_image_name   = "{name}:latest"
      docker_registry_url = "https://${{azurerm_container_registry.main.login_server}}"
    }}
  }}

  app_settings = {{
    DATABASE_URL = "postgresql://${{var.db_admin_login}}:${{var.db_admin_password}}@${{azurerm_postgresql_flexible_server.main.fqdn}}:5432/{tf_name}"
    SECRET_KEY   = var.secret_key
  }}
}}

# -- Azure Database for PostgreSQL ---------------------------------------------

resource "azurerm_postgresql_flexible_server" "main" {{
  name                   = "{name}-db"
  resource_group_name    = azurerm_resource_group.main.name
  location               = azurerm_resource_group.main.location
  version                = "16"
  administrator_login    = var.db_admin_login
  administrator_password = var.db_admin_password
  sku_name               = "B_Standard_B1ms"
  storage_mb             = 32768
}}

resource "azurerm_postgresql_flexible_server_database" "main" {{
  name      = "{tf_name}"
  server_id = azurerm_postgresql_flexible_server.main.id
}}

# -- Container Registry --------------------------------------------------------

resource "azurerm_container_registry" "main" {{
  name                = "{name.replace('-', '')}acr"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = true
}}

# -- Front Door ----------------------------------------------------------------

resource "azurerm_cdn_frontdoor_profile" "main" {{
  name                = "{name}-fd"
  resource_group_name = azurerm_resource_group.main.name
  sku_name            = "Standard_AzureFrontDoor"
}}
"""

    files["terraform/variables.tf"] = f"""variable "location" {{
  default = "West Europe"
}}

variable "db_admin_login" {{
  default = "archie"
}}

variable "db_admin_password" {{
  sensitive = true
}}

variable "secret_key" {{
  sensitive = true
}}
"""

    files["DEPLOY.md"] = f"""# Deployment: Azure (App Service + PostgreSQL + Front Door)

## Prerequisites
- Azure CLI configured (`az login`)
- Terraform >= 1.5

## Steps
```bash
cd terraform
terraform init
terraform plan -var="db_admin_password=YOUR_PASSWORD" -var="secret_key=YOUR_SECRET"
terraform apply

# Build and push to ACR
az acr login --name {name.replace('-', '')}acr
docker build -t {name.replace('-', '')}acr.azurecr.io/{name}:latest .
docker push {name.replace('-', '')}acr.azurecr.io/{name}:latest
```
"""

    return files


def generate_gcp(ctx: dict) -> dict:
    """Generate Terraform configs for GCP Cloud Run + Cloud SQL."""
    solution_id = ctx.get("solution_id", 0)
    name = ctx.get("solution_name", f"solution-{solution_id}").lower().replace(" ", "-")
    tf_name = name.replace("-", "_")
    port = ctx.get("port", 8000)

    files = {}

    files["terraform/main.tf"] = f"""terraform {{
  required_providers {{
    google = {{
      source  = "hashicorp/google"
      version = "~> 5.0"
    }}
  }}
}}

provider "google" {{
  project = var.project_id
  region  = var.region
}}

# -- Cloud SQL -----------------------------------------------------------------

resource "google_sql_database_instance" "main" {{
  name             = "{name}-db"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {{
    tier = "db-f1-micro"
  }}

  deletion_protection = false
}}

resource "google_sql_database" "main" {{
  name     = "{tf_name}"
  instance = google_sql_database_instance.main.name
}}

resource "google_sql_user" "main" {{
  name     = "archie"
  instance = google_sql_database_instance.main.name
  password = var.db_password
}}

# -- Cloud Run -----------------------------------------------------------------

resource "google_cloud_run_v2_service" "main" {{
  name     = "{name}"
  location = var.region

  template {{
    containers {{
      image = "${{var.region}}-docker.pkg.dev/${{var.project_id}}/{name}/{name}:latest"
      ports {{
        container_port = {port}
      }}
      env {{
        name  = "DATABASE_URL"
        value = "postgresql://archie:${{var.db_password}}@/${{google_sql_database.main.name}}?host=/cloudsql/${{google_sql_database_instance.main.connection_name}}"
      }}
    }}

    volumes {{
      name = "cloudsql"
      cloud_sql_instance {{
        instances = [google_sql_database_instance.main.connection_name]
      }}
    }}

    scaling {{
      min_instance_count = 0
      max_instance_count = 10
    }}
  }}
}}

# Allow unauthenticated access (public API)
resource "google_cloud_run_v2_service_iam_member" "public" {{
  name     = google_cloud_run_v2_service.main.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}}
"""

    files["terraform/variables.tf"] = f"""variable "project_id" {{
  description = "GCP project ID"
}}

variable "region" {{
  default = "europe-west1"
}}

variable "db_password" {{
  sensitive = true
}}
"""

    files["DEPLOY.md"] = f"""# Deployment: GCP (Cloud Run + Cloud SQL)

## Prerequisites
- gcloud CLI configured
- Terraform >= 1.5
- Artifact Registry repository created

## Steps
```bash
# Build and push
gcloud auth configure-docker europe-west1-docker.pkg.dev
docker build -t europe-west1-docker.pkg.dev/PROJECT/{name}/{name}:latest .
docker push europe-west1-docker.pkg.dev/PROJECT/{name}/{name}:latest

# Deploy
cd terraform
terraform init
terraform plan -var="project_id=YOUR_PROJECT" -var="db_password=YOUR_PASSWORD"
terraform apply
```
"""

    return files


# -- Dispatcher ----------------------------------------------------------------

GENERATORS = {
    "docker-compose": generate_docker_compose,
    "kubernetes": generate_kubernetes,
    "aws": generate_aws,
    "azure": generate_azure,
    "gcp": generate_gcp,
}


def generate_platform_configs(target_platform: str, ctx: dict) -> dict:
    """Generate deployment configs for the given platform.

    Args:
        target_platform: One of docker-compose, kubernetes, aws, azure, gcp
        ctx: Solution context dict

    Returns:
        Dict of {filepath: content}

    Raises:
        ValueError: If target_platform is unknown.
    """
    gen = GENERATORS.get(target_platform)
    if gen is None:
        raise ValueError(f"Unknown platform: {target_platform}. Valid: {sorted(GENERATORS.keys())}")
    return gen(ctx)
