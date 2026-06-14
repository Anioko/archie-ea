"""
ArchiMate 3.2 Manufacturing Domain Models

Comprehensive domain models for Manufacturing/Production operations with rich
operational attributes specific to Example Corp UK manufacturing facilities.

Design Pattern:
- Each domain model has archimate_element_id foreign key linking to ArchiMateElement
- Domain models contain manufacturing-specific attributes (50 - 80+ fields)
- ArchiMateElement provides metamodel compliance and relationship tracking
- Auto-creates ArchiMateElement on insert via SQLAlchemy event listeners

Models:
- ManufacturingPlant: Physical production facilities (Bristol, etc.)
- ProductionLine: Manufacturing lines within plants (Glass, Coating, Assembly)
- Equipment: Machinery and assets (furnaces, robots, conveyors)
- ProductionOrder: Work orders and production batches
- QualityInspection: Quality control checkpoints and test results
- MaintenanceActivity: Preventive/corrective maintenance tracking
- MaterialInventory: Raw materials and WIP inventory
- ProductionSchedule: Production planning and scheduling
"""

import json
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import event

from .. import db

# ============================================================================
# ManufacturingPlant Domain Model
# ============================================================================


class ManufacturingPlant(db.Model):
    """
    ArchiMate 3.2 Facility (mapped to TechnologyNode) - Physical manufacturing site

    Represents Example Corp UK production facilities with operational attributes.
    Extends ArchiMate with manufacturing plant management capabilities.

    Examples:
    - Bristol Glass Manufacturing Plant (800 people, 24/7 operations)
    - Manchester Coating Facility (350 people, 3 shifts)
    - Scotland Distribution Center (warehouse + light assembly)

    Usage:
        plant = ManufacturingPlant(
            name="Bristol Glass Plant",
            plant_type="Primary Manufacturing",
            location_address="Bristol, UK",
            production_capacity_units_per_day=50000,
            workforce_headcount=800,
            operational_status="Active"
        )
    """

    __tablename__ = "manufacturing_plants"

    id = db.Column(db.Integer, primary_key=True)

    # Core Identity
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    # Link to ArchiMate metamodel (TechnologyNode)
    archimate_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True, index=True
    )

    # Plant Classification
    plant_type = db.Column(
        db.String(50)
    )  # Primary Manufacturing, Secondary Processing, Assembly, Distribution Center, R&D Facility
    manufacturing_category = db.Column(db.String(50))  # Discrete, Process, Batch, Continuous
    product_family = db.Column(
        db.String(100)
    )  # Glass Products, Coatings, Insulation, Construction Materials

    # Location & Geography
    location_address = db.Column(db.String(500))
    city = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    country = db.Column(db.String(100), default="United Kingdom")
    region = db.Column(db.String(100))  # England North, England South, Scotland, Wales
    latitude = db.Column(db.Numeric(10, 7))
    longitude = db.Column(db.Numeric(10, 7))
    site_area_sqm = db.Column(db.Integer)  # Total site area in square meters

    # Operational Status
    operational_status = db.Column(
        db.String(20), default="Active", index=True
    )  # Active, Inactive, Maintenance, Commissioning, Decommissioning
    commissioning_date = db.Column(db.Date)
    last_major_upgrade_date = db.Column(db.Date)
    planned_closure_date = db.Column(db.Date, nullable=True)

    # Production Capacity
    production_capacity_units_per_day = db.Column(db.Integer)  # Theoretical maximum daily output
    actual_production_units_per_day = db.Column(db.Integer)  # Current average daily output
    production_capacity_tonnes_per_year = db.Column(db.Integer)
    number_of_production_lines = db.Column(db.Integer, default=1)

    # Workforce
    workforce_headcount = db.Column(db.Integer)
    production_staff_count = db.Column(db.Integer)
    engineering_staff_count = db.Column(db.Integer)
    quality_staff_count = db.Column(db.Integer)
    maintenance_staff_count = db.Column(db.Integer)
    contractor_count = db.Column(db.Integer, default=0)

    # Shift Operations
    shift_pattern = db.Column(
        db.String(50)
    )  # 24/7 Continuous, 3 - Shift, 2 - Shift, Day Shift Only
    shifts_per_day = db.Column(db.Integer, default=3)
    shift_duration_hours = db.Column(db.Numeric(4, 1), default=8.0)
    operates_weekends = db.Column(db.Boolean, default=True)

    # Financial
    annual_operating_cost = db.Column(db.Numeric(15, 2))
    annual_revenue = db.Column(db.Numeric(15, 2))
    annual_maintenance_budget = db.Column(db.Numeric(12, 2))
    annual_capex_budget = db.Column(db.Numeric(12, 2))
    cost_center = db.Column(db.String(50))

    # Energy & Utilities
    annual_energy_consumption_kwh = db.Column(db.Integer)
    energy_cost_per_kwh = db.Column(db.Numeric(8, 4))
    has_renewable_energy = db.Column(db.Boolean, default=False)
    renewable_energy_percentage = db.Column(db.Numeric(5, 2))
    annual_water_consumption_m3 = db.Column(db.Integer)
    annual_gas_consumption_m3 = db.Column(db.Integer)

    # Environmental & Sustainability
    carbon_footprint_tonnes_co2 = db.Column(db.Integer)
    waste_generated_tonnes_per_year = db.Column(db.Integer)
    waste_recycling_percentage = db.Column(db.Numeric(5, 2))
    iso14001_certified = db.Column(db.Boolean, default=False)  # Environmental management
    environmental_incidents_last_year = db.Column(db.Integer, default=0)

    # Safety & Compliance
    iso9001_certified = db.Column(db.Boolean, default=False)  # Quality management
    iso45001_certified = db.Column(db.Boolean, default=False)  # Occupational health & safety
    last_safety_audit_date = db.Column(db.Date)
    safety_incidents_last_year = db.Column(db.Integer, default=0)
    lost_time_injury_frequency_rate = db.Column(db.Numeric(6, 2))  # LTIFR

    # Performance Metrics
    oee_overall_equipment_effectiveness = db.Column(db.Numeric(5, 2))  # % (0 - 100)
    availability_percentage = db.Column(db.Numeric(5, 2))
    performance_percentage = db.Column(db.Numeric(5, 2))
    quality_percentage = db.Column(db.Numeric(5, 2))
    first_pass_yield = db.Column(db.Numeric(5, 2))  # % products passing first inspection
    scrap_rate_percentage = db.Column(db.Numeric(5, 2))

    # Technology & Systems
    has_mes_system = db.Column(db.Boolean, default=False)  # Manufacturing Execution System
    mes_system_name = db.Column(db.String(100))
    has_scada_system = db.Column(db.Boolean, default=False)  # Supervisory Control
    has_erp_integration = db.Column(db.Boolean, default=True)
    industry_4_0_maturity_level = db.Column(db.Integer)  # 1 - 5 (1=Basic, 5=Fully Digital)

    # Contact & Management
    plant_manager_name = db.Column(db.String(100))
    plant_manager_email = db.Column(db.String(255))
    operations_manager_name = db.Column(db.String(100))
    quality_manager_name = db.Column(db.String(100))

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100))

    # Relationships
    archimate_element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])
    production_lines = db.relationship(
        "ProductionLine", back_populates="plant", cascade="all, delete-orphan"
    )

    # Helper Methods
    @property
    def capacity_utilization(self):
        """Calculate capacity utilization percentage"""
        if self.production_capacity_units_per_day and self.production_capacity_units_per_day > 0:
            return (
                (self.actual_production_units_per_day or 0)
                / self.production_capacity_units_per_day
                * 100
            )
        return 0

    @property
    def total_staff(self):
        """Total workforce including contractors"""
        return (self.workforce_headcount or 0) + (self.contractor_count or 0)

    @property
    def energy_cost_per_unit(self):
        """Energy cost per unit produced"""
        if (
            self.actual_production_units_per_day
            and self.annual_energy_consumption_kwh
            and self.energy_cost_per_kwh
        ):
            annual_units = self.actual_production_units_per_day * 365
            annual_energy_cost = float(self.annual_energy_consumption_kwh) * float(
                self.energy_cost_per_kwh
            )
            return annual_energy_cost / annual_units
        return 0

    def __repr__(self):
        return f"<ManufacturingPlant {self.name}>"


# Event listener for auto-creating ArchiMateElement
@event.listens_for(ManufacturingPlant, "before_insert")
def create_plant_archimate_element(mapper, connection, target):
    """Automatically create ArchiMateElement when ManufacturingPlant is created"""
    if target.archimate_element_id is None:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="Facility",  # ArchiMate TechnologyNode
                layer="Technology",
                description=target.description or f"{target.plant_type} facility",
            )
        )
        target.archimate_element_id = result.inserted_primary_key[0]


# ============================================================================
# ProductionLine Domain Model
# ============================================================================


class ProductionLine(db.Model):
    """
    ArchiMate 3.2 TechnologyProcess - Manufacturing production line

    Represents individual production lines within a plant.
    Each line produces specific products using defined processes.

    Examples:
    - Float Glass Line #1 (Bristol, 600 tonnes/day)
    - Coating Line A (Manchester, 2 - shift operation)
    - Assembly Line 3 (high-mix low-volume)
    """

    __tablename__ = "production_lines"

    id = db.Column(db.Integer, primary_key=True)

    # Core Identity
    name = db.Column(db.String(255), nullable=False, index=True)
    line_code = db.Column(db.String(50), unique=True, index=True)  # GL-BRI - 001
    description = db.Column(db.Text)

    # Link to ArchiMateElement
    archimate_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True, index=True
    )

    # Plant Association
    plant_id = db.Column(
        db.Integer, db.ForeignKey("manufacturing_plants.id"), nullable=False, index=True
    )

    # Line Classification
    line_type = db.Column(
        db.String(50)
    )  # Continuous Flow, Batch, Discrete Assembly, Automated, Manual
    process_type = db.Column(
        db.String(50)
    )  # Forming, Coating, Cutting, Assembly, Packaging, Testing
    production_mode = db.Column(db.String(50))  # Make-to-Stock, Make-to-Order, Configure-to-Order

    # Capacity & Performance
    design_capacity_units_per_hour = db.Column(db.Integer)
    actual_output_units_per_hour = db.Column(db.Integer)
    cycle_time_seconds = db.Column(db.Numeric(10, 2))  # Time per unit
    changeover_time_minutes = db.Column(db.Integer)  # Setup time between products

    # OEE Metrics (Overall Equipment Effectiveness)
    oee_percentage = db.Column(db.Numeric(5, 2))
    availability_percentage = db.Column(db.Numeric(5, 2))  # Uptime
    performance_efficiency = db.Column(db.Numeric(5, 2))  # Speed
    quality_rate = db.Column(db.Numeric(5, 2))  # First-pass yield

    # Operational Status
    operational_status = db.Column(
        db.String(20), default="Running", index=True
    )  # Running, Idle, Setup, Maintenance, Breakdown, Offline
    commissioned_date = db.Column(db.Date)
    last_maintenance_date = db.Column(db.Date)
    next_planned_maintenance = db.Column(db.Date)

    # Staffing
    operators_per_shift = db.Column(db.Integer)
    technicians_assigned = db.Column(db.Integer)
    shift_pattern = db.Column(db.String(50))

    # Products & Materials
    primary_product_code = db.Column(db.String(50))
    capable_product_families = db.Column(db.Text)  # JSON array
    raw_materials_required = db.Column(db.Text)  # JSON array

    # Automation Level
    automation_level = db.Column(
        db.String(50)
    )  # Manual, Semi-Automated, Fully Automated, Lights-Out
    has_plc_control = db.Column(db.Boolean, default=True)  # Programmable Logic Controller
    has_scada_integration = db.Column(db.Boolean, default=False)
    has_vision_inspection = db.Column(db.Boolean, default=False)
    robot_count = db.Column(db.Integer, default=0)

    # Quality
    inline_quality_checks = db.Column(db.Integer, default=0)  # Number of quality stations
    defect_rate_ppm = db.Column(db.Integer)  # Parts per million
    rework_percentage = db.Column(db.Numeric(5, 2))
    scrap_percentage = db.Column(db.Numeric(5, 2))

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    archimate_element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])
    plant = db.relationship("ManufacturingPlant", back_populates="production_lines")
    equipment = db.relationship(
        "Equipment", back_populates="production_line", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<ProductionLine {self.line_code}: {self.name}>"


@event.listens_for(ProductionLine, "before_insert")
def create_line_archimate_element(mapper, connection, target):
    """Auto-create ArchiMateElement for ProductionLine"""
    if target.archimate_element_id is None:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="TechnologyProcess",
                layer="Technology",
                description=target.description or f"{target.line_type} production line",
            )
        )
        target.archimate_element_id = result.inserted_primary_key[0]


# ============================================================================
# Equipment Domain Model
# ============================================================================


class Equipment(db.Model):
    """
    ArchiMate 3.2 Device - Manufacturing equipment and machinery

    Represents individual machines, robots, furnaces, conveyors, etc.
    Tracks maintenance, performance, and criticality.

    Examples:
    - Glass Furnace #1 (critical, £5M asset)
    - Coating Robot ARM - 04 (automated, predictive maintenance)
    - Quality Scanner QS - 12 (inline inspection)
    """

    __tablename__ = "equipment"

    id = db.Column(db.Integer, primary_key=True)

    # Core Identity
    name = db.Column(db.String(255), nullable=False, index=True)
    asset_tag = db.Column(db.String(50), unique=True, index=True)  # EQ-BRI-FUR - 001
    description = db.Column(db.Text)

    # Link to ArchiMateElement
    archimate_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True, index=True
    )

    # Location
    plant_id = db.Column(db.Integer, db.ForeignKey("manufacturing_plants.id"), index=True)
    production_line_id = db.Column(
        db.Integer, db.ForeignKey("production_lines.id"), nullable=True, index=True
    )
    physical_location = db.Column(db.String(200))  # Building A, Zone 3, Station 12

    # Equipment Classification
    equipment_type = db.Column(
        db.String(50)
    )  # Furnace, Robot, Conveyor, Press, Cutter, Scanner, Sensor
    equipment_category = db.Column(
        db.String(50)
    )  # Production, Quality, Material Handling, Utility, Safety
    manufacturer = db.Column(db.String(100))
    model_number = db.Column(db.String(100))
    serial_number = db.Column(db.String(100))

    # Asset Management
    purchase_date = db.Column(db.Date)
    purchase_cost = db.Column(db.Numeric(12, 2))
    depreciation_years = db.Column(db.Integer, default=10)
    current_book_value = db.Column(db.Numeric(12, 2))
    replacement_cost = db.Column(db.Numeric(12, 2))
    expected_end_of_life = db.Column(db.Date)

    # Operational Status
    operational_status = db.Column(
        db.String(20), default="Operating", index=True
    )  # Operating, Idle, Maintenance, Breakdown, Decommissioned
    commissioned_date = db.Column(db.Date)
    last_operated_date = db.Column(db.Date)

    # Performance Metrics
    availability_percentage = db.Column(db.Numeric(5, 2))  # Uptime %
    mtbf_hours = db.Column(db.Integer)  # Mean Time Between Failures
    mttr_hours = db.Column(db.Numeric(6, 2))  # Mean Time To Repair
    utilization_percentage = db.Column(db.Numeric(5, 2))

    # Maintenance
    maintenance_strategy = db.Column(
        db.String(50)
    )  # Reactive, Preventive, Predictive, Condition-Based
    maintenance_interval_hours = db.Column(db.Integer)  # Hours between PM
    last_maintenance_date = db.Column(db.Date)
    next_maintenance_due = db.Column(db.Date)
    total_operating_hours = db.Column(db.Integer, default=0)
    breakdown_count_last_year = db.Column(db.Integer, default=0)

    # Criticality & Risk
    criticality_level = db.Column(db.String(20))  # Critical, High, Medium, Low
    has_redundancy = db.Column(db.Boolean, default=False)
    spare_parts_available = db.Column(db.Boolean, default=True)

    # Technical Specifications
    power_rating_kw = db.Column(db.Numeric(10, 2))
    operating_temperature_max_c = db.Column(db.Integer)
    speed_rpm = db.Column(db.Integer)
    capacity_units_per_hour = db.Column(db.Integer)
    technical_specifications = db.Column(db.Text)  # JSON

    # Connectivity & IoT
    has_sensors = db.Column(db.Boolean, default=False)
    has_plc_connection = db.Column(db.Boolean, default=False)
    has_scada_connection = db.Column(db.Boolean, default=False)
    has_predictive_maintenance = db.Column(db.Boolean, default=False)
    iot_device_id = db.Column(db.String(100))

    # Safety & Compliance
    requires_safety_certification = db.Column(db.Boolean, default=False)
    last_safety_inspection = db.Column(db.Date)
    safety_incidents_count = db.Column(db.Integer, default=0)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    archimate_element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])
    production_line = db.relationship("ProductionLine", back_populates="equipment")

    def __repr__(self):
        return f"<Equipment {self.asset_tag}: {self.name}>"


@event.listens_for(Equipment, "before_insert")
def create_equipment_archimate_element(mapper, connection, target):
    """Auto-create ArchiMateElement for Equipment"""
    if target.archimate_element_id is None:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="Device",
                layer="Technology",
                description=target.description or f"{target.equipment_type} equipment",
            )
        )
        target.archimate_element_id = result.inserted_primary_key[0]


# ============================================================================
# ProductionOrder Domain Model
# ============================================================================


class ProductionOrder(db.Model):
    """
    Production work order / manufacturing batch

    Represents individual production runs on a line.
    Tracks quantity, schedule, status, and actual performance.
    """

    __tablename__ = "production_orders"

    id = db.Column(db.Integer, primary_key=True)

    # Order Identity
    order_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)

    # Production Details
    production_line_id = db.Column(
        db.Integer, db.ForeignKey("production_lines.id"), nullable=False, index=True
    )
    product_code = db.Column(db.String(50), index=True)
    product_description = db.Column(db.String(255))

    # Quantities
    planned_quantity = db.Column(db.Integer, nullable=False)
    actual_quantity_produced = db.Column(db.Integer, default=0)
    good_quantity = db.Column(db.Integer, default=0)
    reject_quantity = db.Column(db.Integer, default=0)
    rework_quantity = db.Column(db.Integer, default=0)

    # Schedule
    planned_start_datetime = db.Column(db.DateTime, index=True)
    planned_end_datetime = db.Column(db.DateTime)
    actual_start_datetime = db.Column(db.DateTime)
    actual_end_datetime = db.Column(db.DateTime)

    # Status
    order_status = db.Column(
        db.String(20), default="Planned", index=True
    )  # Planned, Released, In Progress, Completed, Cancelled
    completion_percentage = db.Column(db.Numeric(5, 2), default=0)

    # Priority
    priority = db.Column(db.String(20), default="Normal")  # Urgent, High, Normal, Low
    customer_order_number = db.Column(db.String(50))

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100))

    def __repr__(self):
        return f"<ProductionOrder {self.order_number}>"


# Add to __init__.py exports
__all__ = ["ManufacturingPlant", "ProductionLine", "Equipment", "ProductionOrder"]
