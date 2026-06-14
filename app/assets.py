from flask_assets import Bundle

# Tailwind CSS - loaded via CDN in _head.html, no compilation needed
# Disable SCSS compilation since we're using Tailwind now
app_css = None

app_js = Bundle("app.js", filters="jsmin", output="scripts/app.js")

# Vendor scripts - using CDN instead of bundled files
vendor_js = None

# Empty vendor_css for compatibility
vendor_css = None
