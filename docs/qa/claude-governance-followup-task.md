# F500-062 independent review follow-up

Your nine focused Chromium tests passed independently. Retain ownership of blueprint.js, the governance partial and focused test/result files only. No commit/deploy, full suite, other workers, package installation or production. Do not edit blueprint.html unless necessary within previous ownership. Coordinator owns CSS and full application tests.

Investigate and reproduce with browser regression tests before fixing:

1. A successful POST followed by failed list GET currently throws from refreshEntityData into submitEntity's save-error catch. It leaves a create form enabled, so retry may duplicate the persisted record. Distinguish successful save from failed refresh; do not invite another POST. Preserve the genuine error and offer an accurate recovery. Keep other entity types unchanged.
2. While a save is pending, Cancel is disabled but Escape, backdrop and modal close still reset state. A delayed response can close or mutate a newly opened editor. Ensure safe pending-save lifecycle, without global modal changes or trapping the user after a request fails. Add a delayed-response browser test.
3. Principle picker currently searches all element types. Use the documented type=Principle query for that picker and test the actual data-array response contract, typed selection and id/name payload. Do not silently replace existing legacy names or free-type entity identifiers. Reject malformed response shapes rather than silently reporting an empty success.

Report any item not completed within the remaining budget. Test only tests/test_blueprint_governance_editor.py. Explicitly retain database/auth/live browser gaps. No baseline relaxation.
