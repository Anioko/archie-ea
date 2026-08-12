/**
 * Business object detail — relate objects, link applications.
 *
 * Every fetch checks `response.ok` and throws on failure. `fetch` does not
 * reject on 4xx/5xx, so an unchecked call turns a 403 into a silent no-op: the
 * user clicks Save, nothing happens, and the architecture quietly does not say
 * what they think it says.
 */
document.addEventListener('alpine:init', function () {
    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    }

    function jsonHeaders() {
        return {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken()
        };
    }

    function toast(kind, message) {
        if (window.Platform && window.Platform.toast && window.Platform.toast[kind]) {
            window.Platform.toast[kind](message);
        }
    }

    Alpine.data('informationObjectDetail', function (config) {
        config = config || {};
        return {
            objectId: config.objectId,
            saving: false,

            // Related-object picker
            objectSearch: '',
            objectResults: [],
            relationshipForm: {
                relationship_type: 'composition',
                target_object_id: null,
                target_object_name: '',
                description: ''
            },

            // Application picker
            applicationSearch: '',
            applicationResults: [],
            applicationForm: {
                application_id: null,
                application_name: '',
                system_role: '',
                notes: ''
            },

            openRelationshipModal() {
                this.objectSearch = '';
                this.objectResults = [];
                this.relationshipForm = {
                    relationship_type: 'composition',
                    target_object_id: null,
                    target_object_name: '',
                    description: ''
                };
                if (window.Platform && window.Platform.modal) {
                    window.Platform.modal.open('relationship-modal');
                }
            },

            openApplicationModal() {
                this.applicationSearch = '';
                this.applicationResults = [];
                this.applicationForm = {
                    application_id: null,
                    application_name: '',
                    system_role: '',
                    notes: ''
                };
                if (window.Platform && window.Platform.modal) {
                    window.Platform.modal.open('application-modal');
                }
            },

            async searchObjects() {
                var term = this.objectSearch.trim();
                if (!term) {
                    this.objectResults = [];
                    return;
                }
                try {
                    var url = '/information-model/api/objects?exclude_id=' + this.objectId +
                        '&q=' + encodeURIComponent(term);
                    var resp = await fetch(url);
                    if (!resp.ok) throw new Error('HTTP ' + resp.status);
                    var data = await resp.json();
                    this.objectResults = data.objects || [];
                } catch (err) {
                    console.error('Business object search failed', err);
                    this.objectResults = [];
                    toast('error', 'Object search failed — that is a lookup failure, not an empty result.');
                }
            },

            selectObject(candidate) {
                this.relationshipForm.target_object_id = candidate.id;
                this.relationshipForm.target_object_name = candidate.name;
                this.objectSearch = candidate.name;
                this.objectResults = [];
            },

            async saveRelationship() {
                if (!this.relationshipForm.target_object_id) {
                    toast('error', 'Pick the object to relate to first.');
                    return;
                }
                this.saving = true;
                try {
                    var resp = await fetch('/information-model/api/relationships', {
                        method: 'POST',
                        headers: jsonHeaders(),
                        body: JSON.stringify({
                            source_object_id: this.objectId,
                            target_object_id: this.relationshipForm.target_object_id,
                            relationship_type: this.relationshipForm.relationship_type,
                            description: this.relationshipForm.description
                        })
                    });
                    var data = await resp.json().catch(function () { return {}; });
                    if (!resp.ok || !data.success) {
                        throw new Error(data.error || ('HTTP ' + resp.status));
                    }
                    toast('success', 'Relationship saved.');
                    window.location.reload();
                } catch (err) {
                    console.error('Failed to relate business objects', err);
                    toast('error', 'Failed to save the relationship: ' + err.message);
                } finally {
                    this.saving = false;
                }
            },

            async removeRelationship(relationshipId) {
                try {
                    var resp = await fetch('/information-model/api/relationships/' + relationshipId, {
                        method: 'DELETE',
                        headers: jsonHeaders()
                    });
                    var data = await resp.json().catch(function () { return {}; });
                    if (!resp.ok || !data.success) {
                        throw new Error(data.error || ('HTTP ' + resp.status));
                    }
                    toast('success', 'Relationship removed.');
                    window.location.reload();
                } catch (err) {
                    console.error('Failed to remove relationship', err);
                    toast('error', 'Failed to remove the relationship: ' + err.message);
                }
            },

            async searchApplications() {
                var term = this.applicationSearch.trim();
                if (!term) {
                    this.applicationResults = [];
                    return;
                }
                try {
                    // The documented application picker endpoint (DESIGN.md).
                    var resp = await fetch(
                        '/applications/api/list?search=' + encodeURIComponent(term) + '&limit=10'
                    );
                    if (!resp.ok) throw new Error('HTTP ' + resp.status);
                    var data = await resp.json();
                    var rows = data.data || data.applications || data.items || [];
                    this.applicationResults = Array.isArray(rows) ? rows : [];
                } catch (err) {
                    console.error('Application search failed', err);
                    this.applicationResults = [];
                    toast('error', 'Application search failed — that is a lookup failure, not an empty result.');
                }
            },

            selectApplication(candidate) {
                this.applicationForm.application_id = candidate.id;
                this.applicationForm.application_name = candidate.name;
                this.applicationSearch = candidate.name;
                this.applicationResults = [];
            },

            async saveApplication() {
                if (!this.applicationForm.application_id) {
                    toast('error', 'Pick an application first.');
                    return;
                }
                this.saving = true;
                try {
                    var resp = await fetch('/information-model/api/applications', {
                        method: 'POST',
                        headers: jsonHeaders(),
                        body: JSON.stringify({
                            business_object_id: this.objectId,
                            application_id: this.applicationForm.application_id,
                            system_role: this.applicationForm.system_role,
                            notes: this.applicationForm.notes
                        })
                    });
                    var data = await resp.json().catch(function () { return {}; });
                    if (!resp.ok || !data.success) {
                        throw new Error(data.error || ('HTTP ' + resp.status));
                    }
                    toast('success', 'Application link saved.');
                    window.location.reload();
                } catch (err) {
                    console.error('Failed to save application link', err);
                    toast('error', 'Failed to save the application link: ' + err.message);
                } finally {
                    this.saving = false;
                }
            },

            async removeApplication(linkId) {
                try {
                    var resp = await fetch('/information-model/api/applications/' + linkId, {
                        method: 'DELETE',
                        headers: jsonHeaders()
                    });
                    var data = await resp.json().catch(function () { return {}; });
                    if (!resp.ok || !data.success) {
                        throw new Error(data.error || ('HTTP ' + resp.status));
                    }
                    toast('success', 'Application link removed.');
                    window.location.reload();
                } catch (err) {
                    console.error('Failed to remove application link', err);
                    toast('error', 'Failed to remove the application link: ' + err.message);
                }
            }
        };
    });
});
