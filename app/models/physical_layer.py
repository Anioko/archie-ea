"""
ArchiMate 3.2 Physical Layer Models

Physical Elements represent the physical infrastructure, hardware, and facilities
that support the technology layer and enable deployment of applications and services.

Physical Layer contains:
- Equipment: Physical computing or network equipment (servers, switches, routers, etc.)
- Facility: A physical location or building
- Distribution Network: Network of connected facilities
- Material: Represents physical materials or resources
"""

from datetime import datetime

from sqlalchemy import event
from sqlalchemy.orm import relationship

from app import db


class PhysicalEquipment(db.Model):
    """ArchiMate 3.2 Equipment - Physical computing or network equipment"""

    __tablename__ = "physical_equipment"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False, index=True)
    description = db.Column(db.Text)
    equipment_type = db.Column(db.String(100))  # Server, Switch, Router, Storage, etc.
    location = db.Column(db.String(256))  # Physical location
    manufacturer = db.Column(db.String(256))
    model_number = db.Column(db.String(256))
    serial_number = db.Column(db.String(256))

    # Operational status
    status = db.Column(db.String(50), default="active")  # active, inactive, decommissioned, planned
    installation_date = db.Column(db.DateTime)
    decommission_date = db.Column(db.DateTime)
    warranty_expiry = db.Column(db.DateTime)

    # Capacity and performance
    cpu_cores = db.Column(db.Integer)
    memory_gb = db.Column(db.Integer)
    storage_gb = db.Column(db.Integer)
    power_consumption_watts = db.Column(db.Integer)

    # ArchiMate relationship
    application_component_id = db.Column(
        db.Integer, db.ForeignKey("application_components.id"), nullable=True
    )
    archimate_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True
    )

    # Relationships
    application_component = relationship("ApplicationComponent", backref="physical_equipment")
    archimate_element = relationship("ArchiMateElement", foreign_keys=[archimate_element_id])

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<PhysicalEquipment {self.name}: {self.equipment_type}>"


class PhysicalFacility(db.Model):
    """ArchiMate 3.2 Facility - Physical location or building"""

    __tablename__ = "physical_facilities"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False, index=True)
    description = db.Column(db.Text)
    facility_type = db.Column(db.String(100))  # DataCenter, Office, WarehouseFactory, etc.
    address = db.Column(db.String(512))
    city = db.Column(db.String(256))
    country = db.Column(db.String(256))
    coordinates = db.Column(db.String(100))  # Latitude,Longitude

    # Capacity and operations
    size_square_meters = db.Column(db.BigInteger)  # Actual column name in database
    capacity = db.Column(db.BigInteger)
    # Note: total_area_sqm, available_area_sqm, power_capacity_kw, cooling_capacity_kw not in current schema

    # Physical location details
    location = db.Column(db.String(512))
    building_name = db.Column(db.String(256))
    floor = db.Column(db.String(50))
    room_number = db.Column(db.String(50))
    postal_code = db.Column(db.String(20))
    latitude = db.Column(db.Numeric)
    longitude = db.Column(db.Numeric)
    owner = db.Column(db.String(256))
    operator = db.Column(db.String(256))
    is_active = db.Column(db.Boolean, default=True)

    # Note: has_redundant_power, has_redundant_cooling, has_fire_suppression, security_level not in current schema
    # Note: power_capacity_kw, cooling_capacity_kw not in current schema

    # Status
    status = db.Column(db.String(50), default="operational")  # operational, planned, decommissioned
    # Note: operational_since, decommission_date not in current schema

    # ArchiMate relationship
    application_component_id = db.Column(
        db.Integer, db.ForeignKey("application_components.id"), nullable=True
    )
    archimate_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True
    )

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<PhysicalFacility {self.name}: {self.facility_type}>"


class PhysicalDistributionNetwork(db.Model):
    """ArchiMate 3.2 Distribution Network - Network of connected facilities"""

    __tablename__ = "physical_distribution_networks"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False, index=True)
    description = db.Column(db.Text)
    network_type = db.Column(db.String(100))  # SupplyChain, Logistics, Telecommunications, etc.

    # Network topology
    hub_facility_id = db.Column(db.Integer, db.ForeignKey("physical_facilities.id"), nullable=True)
    total_nodes = db.Column(db.Integer)
    total_links = db.Column(db.Integer)

    # Performance and reliability
    availability_percentage = db.Column(db.Float)  # 99.9%, 99.99%, etc.
    average_latency_ms = db.Column(db.Integer)
    throughput_mbps = db.Column(db.Integer)

    # Geographic scope
    coverage_area_sqkm = db.Column(db.Float)
    countries_served = db.Column(db.Integer)

    # Status
    status = db.Column(db.String(50), default="operational")
    operational_since = db.Column(db.DateTime)

    # ArchiMate relationship
    application_component_id = db.Column(
        db.Integer, db.ForeignKey("application_components.id"), nullable=True
    )
    archimate_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True
    )

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<PhysicalDistributionNetwork {self.name}: {self.network_type}>"


class PhysicalMaterial(db.Model):
    """ArchiMate 3.2 Material - Physical materials or resources"""

    __tablename__ = "physical_materials"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False, index=True)
    description = db.Column(db.Text)
    material_type = db.Column(db.String(100))  # Paper, Plastic, Metal, Electronic, etc.
    category = db.Column(db.String(100))  # Raw, Processed, Finished, Waste, etc.

    # Physical properties
    unit_of_measure = db.Column(db.String(50))  # kg, liters, pieces, etc.
    density_per_unit = db.Column(db.Float)  # Mass or weight per unit
    cost_per_unit = db.Column(db.Float)

    # Inventory and supply chain
    total_quantity = db.Column(db.Float)
    minimum_quantity = db.Column(db.Float)
    supplier_id = db.Column(db.String(256))  # External supplier ID
    lead_time_days = db.Column(db.Integer)

    # Environmental and compliance
    is_hazardous = db.Column(db.Boolean, default=False)
    recyclable = db.Column(db.Boolean, default=False)
    compliance_certifications = db.Column(db.Text)  # JSON list of certifications
    carbon_footprint_per_unit = db.Column(db.Float)  # kg CO2e

    # Status
    status = db.Column(db.String(50), default="in_stock")  # in_stock, ordered, depleted
    last_restock_date = db.Column(db.DateTime)

    # ArchiMate relationship
    application_component_id = db.Column(
        db.Integer, db.ForeignKey("application_components.id"), nullable=True
    )
    archimate_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True
    )

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<PhysicalMaterial {self.name}: {self.material_type}>"


# Define ArchiMate listener function
def _create_archimate_listener(model_class, element_type):
    @event.listens_for(model_class, "before_insert")
    def listener(mapper, connection, target):
        if target.archimate_element_id is None:
            from sqlalchemy import insert

            from .archimate_core import ArchiMateElement

            result = connection.execute(
                insert(ArchiMateElement.__table__).values(
                    name=target.name,
                    type=element_type,
                    layer="Physical",
                    description=target.description or f"Physical {element_type}",
                )
            )
            target.archimate_element_id = result.inserted_primary_key[0]

    return listener


# Register ArchiMate listeners for automatic sync with ArchiMateElement
_create_archimate_listener(PhysicalEquipment, "Equipment")
_create_archimate_listener(PhysicalFacility, "Facility")
_create_archimate_listener(PhysicalDistributionNetwork, "DistributionNetwork")
_create_archimate_listener(PhysicalMaterial, "Material")
