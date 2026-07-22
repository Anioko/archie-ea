from manage import app
from app import db
with app.app_context():
    from app.models.integration_contract import IntegrationContract
    name = "SAP S4HANA Business Partner"
    ic = IntegrationContract.query.filter_by(name=name).first()
    if not ic:
        ic = IntegrationContract(
            name=name, protocol="odata",
            base_url="https://my-s4hana.example.com/sap/opu/odata/sap/API_BUSINESS_PARTNER_SRV",
            auth_method="named_credential", version="1.0",
            sla_latency_ms=5000, sla_availability="99.5",
        )
        db.session.add(ic); db.session.commit()
    print("IC_OK", ic.id, ic.name, "|", ic.base_url)
