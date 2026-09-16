"""Size bands for effort estimation - see docs/adr/0011-derived-display-bands.md."""

# Thresholds per SRS Assumption A4 -- S <= 40h (~a person-week),
# M 41-160h (~a person-month), L 161-400h (~a person-quarter), XL > 400h
EFFORT_BANDS = ((40, "S"), (160, "M"), (400, "L"))


def effort_band(estimated_effort_hours):
    """Convert estimated effort hours to a T-shirt size band.
    
    >>> effort_band(None) is None
    True
    >>> effort_band(-5) is None
    True
    >>> effort_band(0)
    'S'
    >>> effort_band(40)
    'S'
    >>> effort_band(41)
    'M'
    >>> effort_band(160)
    'M'
    >>> effort_band(161)
    'L'
    >>> effort_band(400)
    'L'
    >>> effort_band(401)
    'XL'
    """
    if estimated_effort_hours is None:
        return None
    
    try:
        hours = float(estimated_effort_hours)
    except (TypeError, ValueError):
        return None
    
    if hours < 0:
        return None
    
    for threshold, label in EFFORT_BANDS:
        if hours <= threshold:
            return label
    
    return "XL"
