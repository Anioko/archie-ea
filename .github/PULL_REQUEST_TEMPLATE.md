<!-- Keep PRs focused on one concern. -->

## What & why

<!-- What does this change, and why? Link any issue: Closes #123 -->

## Checklist

- [ ] Tests pass locally (`pytest -q`) and new behaviour has a test
- [ ] No secrets, internal hostnames/IPs, or real customer data (CI gitleaks gate)
- [ ] No `console.log` / native `alert()`·`confirm()` (use `Platform.toast` / `Platform.modal`)
- [ ] No raw-string `db.session.execute("…")` (wrap in `db.text(...)`)
- [ ] Icon-only buttons have `aria-label`; images have `alt`
- [ ] Staged specific files (not `git add -A`)
