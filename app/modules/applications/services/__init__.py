"""
Application services — consolidated from 11 legacy files (~362KB) into 3 modules.

Modules:
- application_service: Core CRUD, factory, similarity, consolidation, merging, import
- mapping_service:     Architecture mapper, mapping orchestrator, UML adapter
- capability_service:  Capability catalog, mapper, seeder

Usage:
    from app.modules.applications.services.application_service import ApplicationFactory
    from app.modules.applications.services.mapping_service import ApplicationArchitectureMapperService
    from app.modules.applications.services.capability_service import ApplicationCapabilityCatalogService
"""
