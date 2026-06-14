"""Vendor WTForms definitions."""

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    FloatField,
    IntegerField,
    SelectField,
    StringField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, Optional


class CreateVendorForm(FlaskForm):
    """Form for creating/editing a vendor organisation."""

    name = StringField("Vendor Name", validators=[DataRequired(), Length(max=255)])
    display_name = StringField("Display Name", validators=[Optional(), Length(max=255)])
    description = TextAreaField("Description", validators=[Optional()])
    is_active = BooleanField("Active", default=True)
    vendor_type = SelectField(
        "Vendor Type",
        choices=[
            ("", "-- Select --"),
            ("software", "Software"),
            ("hardware", "Hardware"),
            ("services", "Services"),
            ("cloud", "Cloud Provider"),
            ("consulting", "Consulting"),
            ("platform", "Platform"),
            ("other", "Other"),
        ],
        validators=[Optional()],
    )
    website = StringField("Website", validators=[Optional(), Length(max=500)])
    contact_email = StringField("Contact Email", validators=[Optional(), Length(max=255)])
    headquarters_location = StringField(
        "Headquarters Location", validators=[Optional(), Length(max=255)]
    )

    # Analyst positions
    gartner_magic_quadrant_position = SelectField(
        "Gartner MQ Position",
        choices=[
            ("", "-- Select --"),
            ("Leader", "Leader"),
            ("Challenger", "Challenger"),
            ("Visionary", "Visionary"),
            ("Niche Player", "Niche Player"),
        ],
        validators=[Optional()],
    )
    forrester_wave_position = SelectField(
        "Forrester Wave Position",
        choices=[
            ("", "-- Select --"),
            ("Leader", "Leader"),
            ("Strong Performer", "Strong Performer"),
            ("Contender", "Contender"),
            ("Challenger", "Challenger"),
        ],
        validators=[Optional()],
    )

    # Financial / market data
    market_share_percentage = FloatField("Market Share %", validators=[Optional()])
    year_founded = IntegerField("Year Founded", validators=[Optional()])
    employee_count = IntegerField("Employee Count", validators=[Optional()])
    annual_revenue_usd = FloatField("Annual Revenue (USD)", validators=[Optional()])
    customer_count = IntegerField("Customer Count", validators=[Optional()])
    strategic_fit_score = IntegerField("Strategic Fit Score", validators=[Optional()])
    public_company = SelectField(
        "Public Company",
        choices=[("", "-- Select --"), ("yes", "Yes"), ("no", "No")],
        validators=[Optional()],
    )
    stock_symbol = StringField("Stock Symbol", validators=[Optional(), Length(max=20)])

    # Contract info
    strategic_tier = SelectField(
        "Strategic Tier",
        choices=[
            ("", "-- Select --"),
            ("strategic", "Strategic"),
            ("preferred", "Preferred"),
            ("approved", "Approved"),
            ("tactical", "Tactical"),
            ("under_review", "Under Review"),
        ],
        validators=[Optional()],
    )
    contract_status = SelectField(
        "Contract Status",
        choices=[
            ("", "-- Select --"),
            ("active", "Active"),
            ("expiring", "Expiring"),
            ("expired", "Expired"),
            ("pending", "Pending"),
            ("none", "None"),
        ],
        validators=[Optional()],
    )
    contract_start_date = DateField("Contract Start", validators=[Optional()])
    contract_end_date = DateField("Contract End", validators=[Optional()])
    contract_value_annual = FloatField(
        "Annual Contract Value (USD)", validators=[Optional()]
    )
