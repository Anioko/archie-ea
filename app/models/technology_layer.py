"""
ArchiMate 3.2 Technology Layer Domain Models

Comprehensive domain models for Technology Layer elements with rich infrastructure
and operational attributes for infrastructure architecture and technology management.

Design Pattern:
- Each domain model has archimate_element_id foreign key linking to ArchiMateElement
- Domain models contain technology-specific attributes (100+ fields)
- ArchiMateElement provides metamodel compliance and relationship tracking
- Auto-creates ArchiMateElement on insert via SQLAlchemy event listeners

Models:
- Node: Computational or physical resources (servers, VMs, containers)
- Device: Physical IT hardware (routers, switches, load balancers, storage arrays)
- SystemSoftware: Software environments (OS, databases, middleware, containers)
- TechnologyInterface: Points of access to technology services
- Path: Links between nodes (network connections, data flows)
- CommunicationNetwork: Networks for data communication
- TechnologyService: Services offered by technology layer
"""

import json
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, event
from sqlalchemy.orm import relationship, validates

from .. import db

# ============================================================================
# Node Domain Model
# ============================================================================


class Node(db.Model):
    """
    ArchiMate 3.2 Node - Computational or physical resource

    Represents physical servers, virtual machines, containers, compute instances.
    Extends ArchiMate with cloud infrastructure and operational attributes.

    Examples:
    - Physical Server: Dell PowerEdge R750 (Bristol Data Center)
    - Virtual Machine: PROD-WEB - 01 (AWS EC2 t3.large)
    - Container: customer-api-service (Kubernetes pod)
    - Cloud Instance: Azure VM Standard_D4s_v3

    Usage:
        node = Node(
            name="PROD-WEB - 01",
            node_type="Virtual Machine",
            provider="AWS",
            instance_type="t3.large",
            cpu_cores=2,
            memory_gb=8,
            operational_status="production"
        )
    """

    __tablename__ = "technology_nodes"

    id = db.Column(db.Integer, primary_key=True)

    # Core Identity
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    # Link to ArchiMate metamodel
    archimate_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True, index=True
    )

    # Application association
    application_component_id = db.Column(
        db.Integer, db.ForeignKey("application_components.id"), nullable=True, index=True
    )

    # Node Classification
    node_type = db.Column(
        db.String(50), index=True
    )  # Physical Server, Virtual Machine, Container, Cloud Instance, Mainframe, Edge Device
    deployment_model = db.Column(db.String(50))  # On-Premise, Cloud, Hybrid, Edge
    provider = db.Column(db.String(100))  # AWS, Azure, GCP, VMware, Docker, Kubernetes, On-Prem
    instance_type = db.Column(db.String(100))  # t3.large, Standard_D4s_v3, n1 - standard - 4

    # Hardware Specifications
    cpu_cores = db.Column(db.Integer)
    cpu_type = db.Column(db.String(100))  # Intel Xeon Gold 6348, AMD EPYC 7763
    cpu_speed_ghz = db.Column(db.Numeric(5, 2))
    memory_gb = db.Column(db.Integer)
    storage_gb = db.Column(db.Integer)
    storage_type = db.Column(db.String(50))  # SSD, NVMe, HDD, Network Storage
    network_bandwidth_gbps = db.Column(db.Numeric(10, 2))

    # Virtualization
    hypervisor = db.Column(db.String(100))  # VMware ESXi, Hyper-V, KVM, Xen
    cluster_name = db.Column(db.String(200))
    container_runtime = db.Column(db.String(50))  # Docker, containerd, CRI-O
    orchestration_platform = db.Column(db.String(50))  # Kubernetes, Docker Swarm, ECS, AKS

    # Location & Network
    datacenter = db.Column(db.String(200))
    rack_location = db.Column(db.String(100))
    availability_zone = db.Column(db.String(100))
    region = db.Column(db.String(100))  # us-east - 1, eu-west - 2, UK South
    ip_address = db.Column(db.String(45))  # IPv4 or IPv6
    private_ip = db.Column(db.String(45))
    public_ip = db.Column(db.String(45))
    hostname = db.Column(db.String(255))
    fqdn = db.Column(db.String(500))  # Fully Qualified Domain Name

    # Operating System
    os_name = db.Column(db.String(100))  # Ubuntu, RHEL, Windows Server, Amazon Linux
    os_version = db.Column(db.String(50))
    os_architecture = db.Column(db.String(20))  # x86_64, ARM64
    kernel_version = db.Column(db.String(100))
    patch_level = db.Column(db.String(100))
    last_patched_date = db.Column(db.Date)

    # Capacity & Performance
    cpu_utilization_percent = db.Column(db.Numeric(5, 2))
    memory_utilization_percent = db.Column(db.Numeric(5, 2))
    storage_utilization_percent = db.Column(db.Numeric(5, 2))
    network_throughput_mbps = db.Column(db.Integer)
    iops_limit = db.Column(db.Integer)  # Input/Output Operations Per Second

    # High Availability
    is_clustered = db.Column(db.Boolean, default=False)
    cluster_role = db.Column(db.String(50))  # Primary, Secondary, Load Balanced
    failover_node_id = db.Column(db.Integer, db.ForeignKey("technology_nodes.id"), nullable=True)
    load_balancer_id = db.Column(db.Integer, db.ForeignKey("technology_devices.id"), nullable=True)
    backup_node_id = db.Column(db.Integer, db.ForeignKey("technology_nodes.id"), nullable=True)

    # Operational Status
    operational_status = db.Column(
        db.String(20), default="planned"
    )  # planned, provisioning, active, maintenance, decommissioned, failed
    health_status = db.Column(db.String(20))  # Healthy, Warning, Critical, Unknown
    uptime_days = db.Column(db.Integer)
    last_reboot_date = db.Column(db.DateTime)
    maintenance_window = db.Column(db.String(100))  # "Saturdays 02:00 - 04:00 UTC"

    # Lifecycle
    commissioned_date = db.Column(db.Date)
    warranty_expiry_date = db.Column(db.Date)
    decommission_date = db.Column(db.Date, nullable=True)
    refresh_cycle_months = db.Column(db.Integer)  # Expected replacement cycle

    # Cost & Licensing
    monthly_cost = db.Column(db.Numeric(15, 2))
    annual_cost = db.Column(db.Numeric(15, 2))
    cost_center = db.Column(db.String(50))
    license_type = db.Column(db.String(50))  # Reserved Instance, On-Demand, Spot, License Included
    license_expiry_date = db.Column(db.Date)

    # Security & Compliance
    security_group = db.Column(db.String(200))
    firewall_rules = db.Column(db.Text)  # JSON array of firewall rules
    encryption_enabled = db.Column(db.Boolean, default=False)
    encryption_type = db.Column(db.String(50))  # AES - 256, TLS 1.3
    antivirus_installed = db.Column(db.Boolean, default=False)
    vulnerability_scan_date = db.Column(db.Date)
    compliance_tags = db.Column(db.Text)  # JSON: ["PCI-DSS", "GDPR", "SOC2"]

    # Monitoring & Alerts
    monitoring_enabled = db.Column(db.Boolean, default=False)
    monitoring_tool = db.Column(db.String(100))  # CloudWatch, Datadog, Prometheus, Nagios
    alert_threshold_cpu = db.Column(db.Integer, default=80)
    alert_threshold_memory = db.Column(db.Integer, default=85)
    alert_threshold_storage = db.Column(db.Integer, default=90)
    last_alert_date = db.Column(db.DateTime)

    # Backup & Recovery
    backup_enabled = db.Column(db.Boolean, default=False)
    backup_frequency = db.Column(db.String(50))  # Hourly, Daily, Weekly
    backup_retention_days = db.Column(db.Integer)
    last_backup_date = db.Column(db.DateTime)
    disaster_recovery_tier = db.Column(db.String(20))  # Tier 1, Tier 2, Tier 3, Tier 4
    rpo_hours = db.Column(db.Integer)  # Recovery Point Objective
    rto_hours = db.Column(db.Integer)  # Recovery Time Objective

    # Metadata
    tags = db.Column(db.Text)  # JSON: {"Environment": "Production", "Owner": "DevOps"}
    custom_attributes = db.Column(db.Text)  # JSON for extensibility
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100))

    # Relationships
    archimate_element = db.relationship(
        "ArchiMateElement", foreign_keys=[archimate_element_id], backref="technology_node"
    )
    failover_node = db.relationship(
        "Node", remote_side="Node.id", foreign_keys=[failover_node_id], backref="primary_nodes"
    )
    backup_node = db.relationship(
        "Node", remote_side="Node.id", foreign_keys=[backup_node_id], backref="backed_up_nodes"
    )

    # ArchiMate 3.2 Relationships
    physical_models = db.relationship(
        "PhysicalDataModel",
        secondary="physical_model_deployments",
        back_populates="nodes",
        overlaps="physical_models",
    )

    def __repr__(self):
        return f"<Node {self.name} ({self.node_type})>"


# ============================================================================
# Device Domain Model
# ============================================================================


class Device(db.Model):
    """
    ArchiMate 3.2 Device - Physical IT hardware

    Represents routers, switches, load balancers, firewalls, storage arrays.
    Extends ArchiMate with network infrastructure and physical attributes.

    Examples:
    - Router: Cisco ASR 1000 Series
    - Switch: Juniper EX4300 - 48T (Core Switch)
    - Load Balancer: F5 BIG-IP LTM
    - Storage Array: NetApp FAS8200

    Usage:
        device = Device(
            name="CORE-SWITCH - 01",
            device_type="Network Switch",
            manufacturer="Cisco",
            model="Catalyst 9500",
            port_count=48
        )
    """

    __tablename__ = "technology_devices"

    id = db.Column(db.Integer, primary_key=True)

    # Core Identity
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    # Link to ArchiMate metamodel
    archimate_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True, index=True
    )

    # Application association
    application_component_id = db.Column(
        db.Integer, db.ForeignKey("application_components.id"), nullable=True, index=True
    )

    # Device Classification
    device_type = db.Column(
        db.String(50), index=True
    )  # Router, Switch, Load Balancer, Firewall, Storage Array, SAN, NAS, Tape Library
    category = db.Column(db.String(50))  # Network, Storage, Security, Compute
    function = db.Column(db.String(100))  # Core Switch, Edge Router, Perimeter Firewall

    # Manufacturer & Model
    manufacturer = db.Column(db.String(100))  # Cisco, Juniper, F5, NetApp, Dell EMC
    model = db.Column(db.String(200))
    serial_number = db.Column(db.String(100), unique=True)
    asset_tag = db.Column(db.String(100))
    firmware_version = db.Column(db.String(100))
    hardware_revision = db.Column(db.String(50))

    # Physical Specifications
    port_count = db.Column(db.Integer)
    port_speed_gbps = db.Column(db.Numeric(10, 2))  # 1, 10, 25, 40, 100 Gbps
    form_factor = db.Column(db.String(50))  # 1U, 2U, 4U, Tower, Blade
    power_consumption_watts = db.Column(db.Integer)
    cooling_requirements_btu = db.Column(db.Integer)
    weight_kg = db.Column(db.Numeric(10, 2))
    dimensions = db.Column(db.String(100))  # "482mm x 450mm x 44mm"

    # Capacity & Performance
    throughput_gbps = db.Column(db.Numeric(10, 2))
    packet_forwarding_rate_mpps = db.Column(db.Numeric(10, 2))  # Million Packets Per Second
    max_connections = db.Column(db.Integer)
    storage_capacity_tb = db.Column(db.Numeric(10, 2))
    iops_capacity = db.Column(db.Integer)

    # Location & Network
    datacenter = db.Column(db.String(200))
    rack_location = db.Column(db.String(100))
    rack_unit_position = db.Column(db.String(20))  # U1 - U4
    management_ip = db.Column(db.String(45))
    management_interface = db.Column(db.String(100))
    vlan_config = db.Column(db.Text)  # JSON array of VLAN configurations

    # Network Configuration (for network devices)
    routing_protocol = db.Column(db.String(50))  # BGP, OSPF, EIGRP, Static
    routing_table_size = db.Column(db.Integer)
    mac_address_table_size = db.Column(db.Integer)
    spanning_tree_protocol = db.Column(db.String(50))  # STP, RSTP, MSTP
    link_aggregation = db.Column(db.Boolean, default=False)
    jumbo_frames_enabled = db.Column(db.Boolean, default=False)

    # Storage Configuration (for storage devices)
    raid_level = db.Column(db.String(20))  # RAID 0, 1, 5, 6, 10, 50, 60
    disk_count = db.Column(db.Integer)
    disk_type = db.Column(db.String(50))  # SSD, SAS, NL-SAS, SATA
    usable_capacity_tb = db.Column(db.Numeric(10, 2))
    compression_enabled = db.Column(db.Boolean, default=False)
    deduplication_enabled = db.Column(db.Boolean, default=False)
    snapshot_capability = db.Column(db.Boolean, default=False)
    replication_enabled = db.Column(db.Boolean, default=False)

    # Security Features (for security devices)
    firewall_throughput_gbps = db.Column(db.Numeric(10, 2))
    vpn_throughput_gbps = db.Column(db.Numeric(10, 2))
    ips_throughput_gbps = db.Column(db.Numeric(10, 2))
    concurrent_sessions = db.Column(db.Integer)
    threat_intelligence_enabled = db.Column(db.Boolean, default=False)
    ssl_inspection_enabled = db.Column(db.Boolean, default=False)

    # High Availability
    is_redundant = db.Column(db.Boolean, default=False)
    redundancy_pair_id = db.Column(
        db.Integer, db.ForeignKey("technology_devices.id"), nullable=True
    )
    failover_mode = db.Column(db.String(50))  # Active-Passive, Active-Active
    power_supply_count = db.Column(db.Integer)
    power_supply_redundant = db.Column(db.Boolean, default=False)
    fan_count = db.Column(db.Integer)
    fan_redundancy = db.Column(db.Boolean, default=False)

    # Operational Status
    operational_status = db.Column(
        db.String(20), default="active"
    )  # active, standby, maintenance, failed, decommissioned
    health_status = db.Column(db.String(20))  # Healthy, Degraded, Critical
    uptime_days = db.Column(db.Integer)
    last_reboot_date = db.Column(db.DateTime)
    temperature_celsius = db.Column(db.Integer)
    cpu_utilization_percent = db.Column(db.Numeric(5, 2))
    memory_utilization_percent = db.Column(db.Numeric(5, 2))

    # Lifecycle
    purchase_date = db.Column(db.Date)
    installation_date = db.Column(db.Date)
    warranty_expiry_date = db.Column(db.Date)
    support_contract_expiry = db.Column(db.Date)
    eol_date = db.Column(db.Date)  # End of Life
    eos_date = db.Column(db.Date)  # End of Support
    decommission_date = db.Column(db.Date, nullable=True)

    # Cost & Procurement
    purchase_cost = db.Column(db.Numeric(15, 2))
    annual_maintenance_cost = db.Column(db.Numeric(15, 2))
    cost_center = db.Column(db.String(50))
    vendor = db.Column(db.String(200))
    purchase_order = db.Column(db.String(100))

    # Monitoring & Management
    monitoring_enabled = db.Column(db.Boolean, default=False)
    snmp_enabled = db.Column(db.Boolean, default=False)
    snmp_community = db.Column(db.String(100))
    syslog_server = db.Column(db.String(255))
    ntp_server = db.Column(db.String(255))
    management_tool = db.Column(db.String(100))  # Cisco DNA Center, SolarWinds, PRTG

    # Configuration Management
    config_backup_enabled = db.Column(db.Boolean, default=False)
    last_config_backup = db.Column(db.DateTime)
    config_repository = db.Column(db.String(500))  # Git repo URL
    change_control_required = db.Column(db.Boolean, default=True)

    # Metadata
    tags = db.Column(db.Text)  # JSON
    custom_attributes = db.Column(db.Text)  # JSON for extensibility
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100))

    # Relationships
    archimate_element = db.relationship(
        "ArchiMateElement", foreign_keys=[archimate_element_id], backref="technology_device"
    )
    redundancy_pair = db.relationship(
        "Device",
        remote_side="Device.id",
        foreign_keys=[redundancy_pair_id],
        backref="redundant_devices",
    )

    def __repr__(self):
        return f"<Device {self.name} ({self.device_type})>"


# ============================================================================
# SystemSoftware Domain Model
# ============================================================================


class SystemSoftware(db.Model):
    """
    ArchiMate 3.2 System Software - Software environment providing execution platform

    Represents operating systems, databases, middleware, container runtimes, application servers.
    Extends ArchiMate with licensing, patching, and operational attributes.

    Examples:
    - Operating System: Red Hat Enterprise Linux 8.5
    - Database: Oracle Database 19c Enterprise Edition
    - Middleware: IBM WebSphere 9.0
    - Container Runtime: Docker Engine 20.10

    Usage:
        software = SystemSoftware(
            name="PostgreSQL 14",
            software_type="Database",
            vendor="PostgreSQL Global Development Group",
            version="14.5",
            license_type="Open Source"
        )
    """

    __tablename__ = "technology_system_software"

    id = db.Column(db.Integer, primary_key=True)

    # Core Identity
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    # Link to ArchiMate metamodel
    archimate_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True, index=True
    )

    # Application association
    application_component_id = db.Column(
        db.Integer, db.ForeignKey("application_components.id"), nullable=True, index=True
    )

    # Software Classification
    software_type = db.Column(
        db.String(50), index=True
    )  # Operating System, Database, Middleware, Application Server, Web Server, Container Runtime, Message Broker, Cache, Search Engine
    category = db.Column(db.String(50))  # System, Infrastructure, Platform
    function = db.Column(
        db.String(100)
    )  # Execution Environment, Data Storage, Integration Platform

    # Vendor & Version
    vendor = db.Column(db.String(200))  # Microsoft, Oracle, Red Hat, PostgreSQL, Docker
    product_name = db.Column(db.String(200))
    version = db.Column(db.String(100), index=True)
    edition = db.Column(db.String(100))  # Enterprise, Standard, Community, Express
    build_number = db.Column(db.String(100))
    release_date = db.Column(db.Date)

    # Installation
    installed_on_node_id = db.Column(
        db.Integer, db.ForeignKey("technology_nodes.id"), nullable=True
    )
    installation_path = db.Column(db.String(500))
    installation_date = db.Column(db.Date)
    installed_by = db.Column(db.String(100))
    installation_size_gb = db.Column(db.Numeric(10, 2))

    # Licensing
    license_type = db.Column(
        db.String(50)
    )  # Commercial, Open Source, Proprietary, Subscription, Perpetual
    license_model = db.Column(
        db.String(50)
    )  # Per Core, Per Socket, Per User, Per Device, Enterprise
    license_count = db.Column(db.Integer)
    license_key = db.Column(db.String(500))  # Encrypted
    license_expiry_date = db.Column(db.Date)
    license_cost_annual = db.Column(db.Numeric(15, 2))
    maintenance_cost_annual = db.Column(db.Numeric(15, 2))
    support_tier = db.Column(db.String(50))  # Basic, Standard, Premium, 24x7

    # Configuration
    config_file_path = db.Column(db.String(500))
    config_parameters = db.Column(db.Text)  # JSON of key configuration settings
    environment_variables = db.Column(db.Text)  # JSON
    startup_command = db.Column(db.String(500))
    service_account = db.Column(db.String(100))

    # Database Specific (if database)
    database_engine = db.Column(db.String(50))  # PostgreSQL, MySQL, Oracle, SQL Server, MongoDB
    database_size_gb = db.Column(db.Numeric(15, 2))
    max_connections = db.Column(db.Integer)
    connection_pool_size = db.Column(db.Integer)
    replication_enabled = db.Column(db.Boolean, default=False)
    replication_mode = db.Column(db.String(50))  # Master-Slave, Master-Master, Cluster
    backup_frequency = db.Column(db.String(50))  # Hourly, Daily, Weekly
    last_backup_date = db.Column(db.DateTime)

    # Middleware Specific
    protocol_support = db.Column(db.Text)  # JSON: ["HTTP", "HTTPS", "JMS", "AMQP"]
    port_numbers = db.Column(db.Text)  # JSON: [8080, 8443]
    clustering_enabled = db.Column(db.Boolean, default=False)
    cluster_members = db.Column(db.Text)  # JSON array of node names
    load_balancing_method = db.Column(db.String(50))  # Round Robin, Least Connections, IP Hash

    # Performance & Capacity
    memory_allocated_gb = db.Column(db.Integer)
    memory_usage_gb = db.Column(db.Numeric(10, 2))
    cpu_cores_allocated = db.Column(db.Integer)
    cpu_utilization_percent = db.Column(db.Numeric(5, 2))
    max_throughput_tps = db.Column(db.Integer)  # Transactions per second
    current_throughput_tps = db.Column(db.Integer)
    max_concurrent_users = db.Column(db.Integer)

    # Operational Status
    operational_status = db.Column(
        db.String(20), default="active"
    )  # active, stopped, maintenance, failed
    service_status = db.Column(db.String(20))  # Running, Stopped, Starting, Stopping
    health_status = db.Column(db.String(20))  # Healthy, Degraded, Critical
    uptime_hours = db.Column(db.Integer)
    last_restart_date = db.Column(db.DateTime)
    last_crash_date = db.Column(db.DateTime)

    # Patching & Updates
    patch_level = db.Column(db.String(100))
    last_patched_date = db.Column(db.Date)
    pending_patches = db.Column(db.Text)  # JSON array of pending patch IDs
    auto_update_enabled = db.Column(db.Boolean, default=False)
    patch_schedule = db.Column(db.String(100))  # "Monthly, Second Saturday"

    # Security
    security_hardening_applied = db.Column(db.Boolean, default=False)
    hardening_standard = db.Column(db.String(100))  # CIS Benchmark, STIG
    vulnerability_scan_date = db.Column(db.Date)
    critical_vulnerabilities = db.Column(db.Integer, default=0)
    ssl_tls_enabled = db.Column(db.Boolean, default=False)
    ssl_certificate_expiry = db.Column(db.Date)
    authentication_method = db.Column(db.String(100))  # Local, LDAP, Active Directory, OAuth

    # Monitoring & Logging
    monitoring_enabled = db.Column(db.Boolean, default=False)
    monitoring_tool = db.Column(db.String(100))  # Prometheus, Datadog, New Relic
    log_level = db.Column(db.String(20))  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_file_path = db.Column(db.String(500))
    log_rotation_policy = db.Column(db.String(100))  # Daily, Weekly, Size-based
    centralized_logging = db.Column(db.Boolean, default=False)
    log_aggregator = db.Column(db.String(100))  # Splunk, ELK, CloudWatch Logs

    # High Availability
    is_clustered = db.Column(db.Boolean, default=False)
    cluster_name = db.Column(db.String(200))
    cluster_role = db.Column(db.String(50))  # Primary, Secondary, Arbiter
    failover_enabled = db.Column(db.Boolean, default=False)
    failover_time_seconds = db.Column(db.Integer)

    # Lifecycle
    eol_date = db.Column(db.Date)  # End of Life
    eos_date = db.Column(db.Date)  # End of Support
    upgrade_path = db.Column(db.String(200))  # "14.x -> 15.x -> 16.x"
    next_upgrade_date = db.Column(db.Date)
    decommission_date = db.Column(db.Date, nullable=True)

    # Dependencies
    depends_on_software = db.Column(db.Text)  # JSON array of other SystemSoftware IDs
    required_by_applications = db.Column(db.Text)  # JSON array of application names

    # Compliance & Governance
    compliance_tags = db.Column(db.Text)  # JSON: ["PCI-DSS", "HIPAA"]
    change_control_required = db.Column(db.Boolean, default=True)
    backup_required = db.Column(db.Boolean, default=True)
    disaster_recovery_tier = db.Column(db.String(20))

    # Metadata
    tags = db.Column(db.Text)  # JSON
    custom_attributes = db.Column(db.Text)  # JSON for extensibility
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100))

    # Relationships
    archimate_element = db.relationship(
        "ArchiMateElement",
        foreign_keys=[archimate_element_id],
        backref="technology_system_software",
    )
    installed_on_node = db.relationship(
        "Node", foreign_keys=[installed_on_node_id], backref="installed_software"
    )

    # ArchiMate 3.2 Relationships
    physical_models = db.relationship(
        "PhysicalDataModel",
        secondary="physical_model_deployments",
        back_populates="system_softwares",
        overlaps="physical_models",
    )

    def __repr__(self):
        return f"<SystemSoftware {self.name} {self.version}>"


# ============================================================================
# TechnologyInterface Domain Model
# ============================================================================


class TechnologyInterface(db.Model):
    """
    ArchiMate 3.2 Technology Interface - Point of access to technology services

    Represents network interfaces, API endpoints, database connections, storage mounts.
    Extends ArchiMate with network and connectivity attributes.

    Usage:
        interface = TechnologyInterface(
            name="eth0",
            interface_type="Network Interface",
            protocol="TCP/IP",
            port_number=443
        )
    """

    __tablename__ = "technology_interfaces"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    archimate_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True, index=True
    )

    # Application association
    application_component_id = db.Column(
        db.Integer, db.ForeignKey("application_components.id"), nullable=True, index=True
    )

    # Interface Classification
    interface_type = db.Column(
        db.String(50), index=True
    )  # Network Interface, API Endpoint, Database Connection, Storage Mount, Message Queue
    protocol = db.Column(db.String(50))  # TCP/IP, HTTP, HTTPS, FTP, NFS, CIFS, iSCSI
    port_number = db.Column(db.Integer)

    # Network Interface Details
    mac_address = db.Column(db.String(17))
    ip_address = db.Column(db.String(45))
    subnet_mask = db.Column(db.String(45))
    gateway = db.Column(db.String(45))
    dns_servers = db.Column(db.Text)  # JSON array
    vlan_id = db.Column(db.Integer)
    speed_mbps = db.Column(db.Integer)
    duplex_mode = db.Column(db.String(20))  # Full, Half
    mtu_size = db.Column(db.Integer, default=1500)

    # Connectivity
    connected_to_node_id = db.Column(
        db.Integer, db.ForeignKey("technology_nodes.id"), nullable=True
    )
    connected_to_device_id = db.Column(
        db.Integer, db.ForeignKey("technology_devices.id"), nullable=True
    )
    physical_port = db.Column(db.String(50))
    cable_type = db.Column(db.String(50))  # Cat6, Fiber, Wireless

    # Status & Monitoring
    operational_status = db.Column(db.String(20), default="active")
    admin_status = db.Column(db.String(20), default="enabled")  # enabled, disabled
    bandwidth_utilization_percent = db.Column(db.Numeric(5, 2))
    packet_loss_percent = db.Column(db.Numeric(5, 2))
    latency_ms = db.Column(db.Integer)

    # Metadata
    tags = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    archimate_element = db.relationship(
        "ArchiMateElement", foreign_keys=[archimate_element_id], backref="technology_interface"
    )
    connected_node = db.relationship(
        "Node", foreign_keys=[connected_to_node_id], backref="interfaces"
    )
    connected_device = db.relationship(
        "Device", foreign_keys=[connected_to_device_id], backref="interfaces"
    )

    def __repr__(self):
        return f"<TechnologyInterface {self.name}>"


# ============================================================================
# Path Domain Model
# ============================================================================


class Path(db.Model):
    """
    ArchiMate 3.2 Path - Link between nodes for communication

    Represents network connections, data flows, communication channels.
    """

    __tablename__ = "technology_paths"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    archimate_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True, index=True
    )

    # Path Classification
    path_type = db.Column(db.String(50))  # Physical Link, Logical Connection, VPN Tunnel, Data Flow
    protocol = db.Column(db.String(50))  # TCP, UDP, MPLS, IPSec, GRE

    # Endpoints
    source_node_id = db.Column(db.Integer, db.ForeignKey("technology_nodes.id"), nullable=True)
    target_node_id = db.Column(db.Integer, db.ForeignKey("technology_nodes.id"), nullable=True)
    source_interface_id = db.Column(
        db.Integer, db.ForeignKey("technology_interfaces.id"), nullable=True
    )
    target_interface_id = db.Column(
        db.Integer, db.ForeignKey("technology_interfaces.id"), nullable=True
    )

    # Path Characteristics
    bandwidth_mbps = db.Column(db.Integer)
    latency_ms = db.Column(db.Integer)
    jitter_ms = db.Column(db.Integer)
    packet_loss_percent = db.Column(db.Numeric(5, 2))

    # Status
    operational_status = db.Column(db.String(20), default="active")
    health_status = db.Column(db.String(20))  # Healthy, Degraded, Down
    utilization_percent = db.Column(db.Numeric(5, 2))

    # Metadata
    tags = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    archimate_element = db.relationship(
        "ArchiMateElement", foreign_keys=[archimate_element_id], backref="technology_path"
    )
    source_node = db.relationship("Node", foreign_keys=[source_node_id], backref="outgoing_paths")
    target_node = db.relationship("Node", foreign_keys=[target_node_id], backref="incoming_paths")

    def __repr__(self):
        return f"<Path {self.name}>"


# ============================================================================
# CommunicationNetwork Domain Model
# ============================================================================


class CommunicationNetwork(db.Model):
    """
    ArchiMate 3.2 Communication Network - Network for data communication

    Represents LANs, WANs, VPNs, Internet, private networks.
    """

    __tablename__ = "technology_communication_networks"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    archimate_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True, index=True
    )

    # Network Classification
    network_type = db.Column(
        db.String(50), index=True
    )  # LAN, WAN, MAN, Internet, Intranet, VPN, VLAN, SD-WAN
    topology = db.Column(db.String(50))  # Star, Mesh, Ring, Bus, Hybrid

    # Network Details
    network_address = db.Column(db.String(50))  # 10.0.0.0/8, 192.168.1.0/24
    subnet_mask = db.Column(db.String(45))
    vlan_id = db.Column(db.Integer)
    vrf_name = db.Column(db.String(100))  # Virtual Routing and Forwarding

    # Characteristics
    bandwidth_gbps = db.Column(db.Numeric(10, 2))
    redundancy_level = db.Column(db.String(50))  # None, Dual, Triple
    encryption_enabled = db.Column(db.Boolean, default=False)
    qos_enabled = db.Column(db.Boolean, default=False)  # Quality of Service

    # Geographic
    geographic_scope = db.Column(db.String(100))  # Site, Campus, Regional, National, Global
    locations = db.Column(db.Text)  # JSON array of locations

    # Service Provider
    provider = db.Column(db.String(200))
    circuit_id = db.Column(db.String(100))
    service_level_agreement = db.Column(db.Text)
    monthly_cost = db.Column(db.Numeric(15, 2))

    # Status
    operational_status = db.Column(db.String(20), default="active")
    health_status = db.Column(db.String(20))
    utilization_percent = db.Column(db.Numeric(5, 2))

    # Metadata
    tags = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    archimate_element = db.relationship(
        "ArchiMateElement",
        foreign_keys=[archimate_element_id],
        backref="technology_communication_network",
    )

    def __repr__(self):
        return f"<CommunicationNetwork {self.name}>"


# ============================================================================
# TechnologyService Domain Model
# ============================================================================


class TechnologyService(db.Model):
    """
    ArchiMate 3.2 Technology Service - Externally visible unit of technology functionality

    Represents infrastructure services like compute, storage, network services.
    """

    __tablename__ = "technology_services"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    archimate_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True, index=True
    )

    # Application association
    application_component_id = db.Column(
        db.Integer, db.ForeignKey("application_components.id"), nullable=True, index=True
    )

    # Service Classification
    service_type = db.Column(
        db.String(50), index=True
    )  # Compute, Storage, Network, Database, Backup, Security
    service_category = db.Column(db.String(50))  # IaaS, PaaS, Managed Service

    # Service Details
    service_provider = db.Column(db.String(200))
    service_tier = db.Column(db.String(50))  # Basic, Standard, Premium
    sla_percentage = db.Column(db.Numeric(5, 2))  # 99.9%, 99.99%

    # Capacity
    capacity_unit = db.Column(db.String(50))  # vCPU, GB, TB, IOPS, Requests/sec
    capacity_allocated = db.Column(db.Numeric(15, 2))
    capacity_used = db.Column(db.Numeric(15, 2))

    # Cost
    pricing_model = db.Column(db.String(50))  # Pay-as-you-go, Reserved, Spot, Fixed
    hourly_cost = db.Column(db.Numeric(10, 4))
    monthly_cost = db.Column(db.Numeric(15, 2))

    # Status
    operational_status = db.Column(db.String(20), default="active")
    availability_zone = db.Column(db.String(100))

    # Metadata
    tags = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    archimate_element = db.relationship(
        "ArchiMateElement", foreign_keys=[archimate_element_id], backref="technology_service"
    )

    def __repr__(self):
        return f"<TechnologyService {self.name}>"


# ============================================================================
# Event Listeners for ArchiMate Element Auto-creation
# ============================================================================


@event.listens_for(Node, "before_insert")
def create_node_archimate_element(mapper, connection, target):
    """Auto-create ArchiMateElement when Node is created"""
    if target.archimate_element_id is None:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="Node",
                layer="Technology",
                description=target.description or f"{target.node_type} node",
            )
        )
        target.archimate_element_id = result.inserted_primary_key[0]


@event.listens_for(Device, "before_insert")
def create_device_archimate_element(mapper, connection, target):
    """Auto-create ArchiMateElement when Device is created"""
    if target.archimate_element_id is None:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="Device",
                layer="Technology",
                description=target.description or f"{target.device_type} device",
            )
        )
        target.archimate_element_id = result.inserted_primary_key[0]


@event.listens_for(SystemSoftware, "before_insert")
def create_systemsoftware_archimate_element(mapper, connection, target):
    """Auto-create ArchiMateElement when SystemSoftware is created"""
    if target.archimate_element_id is None:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="SystemSoftware",
                layer="Technology",
                description=target.description or f"{target.software_type}",
            )
        )
        target.archimate_element_id = result.inserted_primary_key[0]


@event.listens_for(TechnologyInterface, "before_insert")
def create_technologyinterface_archimate_element(mapper, connection, target):
    """Auto-create ArchiMateElement when TechnologyInterface is created"""
    if target.archimate_element_id is None:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="TechnologyInterface",
                layer="Technology",
                description=target.description or "Technology interface",
            )
        )
        target.archimate_element_id = result.inserted_primary_key[0]


@event.listens_for(Path, "before_insert")
def create_path_archimate_element(mapper, connection, target):
    """Auto-create ArchiMateElement when Path is created"""
    if target.archimate_element_id is None:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="Path",
                layer="Technology",
                description=target.description or "Communication path",
            )
        )
        target.archimate_element_id = result.inserted_primary_key[0]


@event.listens_for(CommunicationNetwork, "before_insert")
def create_communicationnetwork_archimate_element(mapper, connection, target):
    """Auto-create ArchiMateElement when CommunicationNetwork is created"""
    if target.archimate_element_id is None:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="CommunicationNetwork",
                layer="Technology",
                description=target.description or f"{target.network_type} network",
            )
        )
        target.archimate_element_id = result.inserted_primary_key[0]


@event.listens_for(TechnologyService, "before_insert")
def create_technologyservice_archimate_element(mapper, connection, target):
    """Auto-create ArchiMateElement when TechnologyService is created"""
    if target.archimate_element_id is None:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="TechnologyService",
                layer="Technology",
                description=target.description or f"{target.service_type} service",
            )
        )
        target.archimate_element_id = result.inserted_primary_key[0]


# ============================================================================
# TechnologyArtifact Domain Model (Deployment)
# ============================================================================


class TechnologyArtifact(db.Model):
    """
    ArchiMate 3.2 Artifact - A piece of data that is used or produced in a software development
    process, or by deployment and operation of a system.

    Examples:
    - "Model.jar"
    - "Source Code File"
    - "Application Log"
    - "Container Image"
    """

    __tablename__ = "technology_artifacts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    # ArchiMate Linkage
    archimate_element_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"))

    # Artifact Specifics
    artifact_type = db.Column(db.String(50))  # File, Executable, Archive, Image, Log
    version = db.Column(db.String(50))
    file_path = db.Column(db.String(500))

    # Deployment
    deployed_on_node_id = db.Column(db.Integer, db.ForeignKey("technology_nodes.id"))

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    archimate_element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])
    deployed_on_node = db.relationship("Node", foreign_keys=[deployed_on_node_id])

    # ArchiMate 3.2 Relationships
    physical_models = db.relationship(
        "PhysicalDataModel", secondary="physical_model_artifacts", back_populates="artifacts"
    )

    def __repr__(self):
        return f"<TechnologyArtifact {self.name}>"


@event.listens_for(TechnologyArtifact, "before_insert")
def create_artifact_archimate_element(mapper, connection, target):
    """Auto-create ArchiMateElement for TechnologyArtifact"""
    if target.archimate_element_id is None:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="Artifact",
                layer="Technology",
                description=target.description or f"Artifact: {target.name}",
            )
        )
        target.archimate_element_id = result.inserted_primary_key[0]


# ============================================================================
# TechnologyCollaboration Domain Model
# ============================================================================


class TechnologyCollaboration(db.Model):
    """
    ArchiMate 3.2 Technology Collaboration - An aggregate of two or more nodes that work together
    to perform collective technology behavior.

    Examples:
    - "Mainframe Cluster"
    - "High Availability Database Cluster"
    - "Load Balanced Web Server Group"
    """

    __tablename__ = "technology_collaborations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    # ArchiMate Linkage
    archimate_element_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"))

    # Collaboration Specifics
    collaboration_type = db.Column(db.String(50))  # Cluster, Grid, Cloud, Hybrid
    redundancy_mode = db.Column(db.String(50))  # Active-Active, Active-Passive

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    archimate_element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])

    def __repr__(self):
        return f"<TechnologyCollaboration {self.name}>"


@event.listens_for(TechnologyCollaboration, "before_insert")
def create_collaboration_archimate_element(mapper, connection, target):
    """Auto-create ArchiMateElement for TechnologyCollaboration"""
    if target.archimate_element_id is None:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="TechnologyCollaboration",
                layer="Technology",
                description=target.description or f"Technology Collaboration: {target.name}",
            )
        )
        target.archimate_element_id = result.inserted_primary_key[0]
