"""Browser-audit entrypoint with submission protection enabled.

Keep the isolated testing database and test-only rate-limit exemption, but do
not bypass CSRF: the audit must see the tokens and enforcement users receive.
This entrypoint is used only by the whole-product audit subprocess.
"""


def create_app():
    from manage import app

    app.config["WTF_CSRF_ENABLED"] = True
    return app
