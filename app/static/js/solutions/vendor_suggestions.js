// app/static/js/solutions/vendor_suggestions.js
// Alpine.js mixin for vendor suggestion cards in journey wizard Step 2
// Included by: app/static/js/architecture_assistant/journey_v2.js (spread into journeyV2Flow)
// API: GET /api/solutions/<id>/suggestions/vendors?capability_ids=<ids>
//      POST /api/solutions/<id>/suggestions/vendors/confirm
// Uses var/function style per codebase convention

function vendorSuggestionsMixin() {
    return {
        vendorSuggestions: [],
        vendorLoading: false,
        vendorError: null,

        fetchVendorSuggestions: function(solutionId, capabilityIds) {
            let self = this;
            if (!solutionId || !capabilityIds || capabilityIds.length === 0) return;
            self.vendorLoading = true;
            self.vendorError = null;

            const params = capabilityIds.join(',');
            fetch('/api/solutions/' + solutionId + '/suggestions/vendors?capability_ids=' + params, {
                credentials: 'same-origin',
                headers: (function() {
                    const h = {};
                    let csrf = document.querySelector('meta[name=csrf-token]');
                    if (csrf) h['X-CSRFToken'] = csrf.content;
                    return h;
                }())
            })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    // Unwrap api_success envelope if present
                    let payload = (data && data.data !== undefined) ? data.data : data;
                    self.vendorSuggestions = payload.capability_suggestions || [];
                    self.vendorLoading = false;
                })
                .catch(function(err) {
                    self.vendorError = 'Failed to load vendor suggestions';
                    self.vendorLoading = false;
                    console.error('Vendor suggestions error:', err);
                });
        },

        confirmVendor: function(solutionId, pricingId, index, vendorIndex) {
            let self = this;
            let csrf = document.querySelector('meta[name=csrf-token]');
            let headers = {'Content-Type': 'application/json'};
            if (csrf) headers['X-CSRFToken'] = csrf.content;

            fetch('/api/solutions/' + solutionId + '/suggestions/vendors/confirm', {
                method: 'POST',
                credentials: 'same-origin',
                headers: headers,
                body: JSON.stringify({pricing_id: pricingId})
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                let payload = (data && data.data !== undefined) ? data.data : data;
                if (payload.success) {
                    let suggestion = self.vendorSuggestions[index];
                    if (suggestion && suggestion.vendors && suggestion.vendors[vendorIndex]) {
                        suggestion.vendors[vendorIndex].data_source_type = 'architect_confirmed';
                        suggestion.vendors[vendorIndex].confirmed_by_count = payload.confirmed_by_count;
                    }
                }
            })
            .catch(function(err) {
                console.error('Vendor confirm error:', err);
            });
        },

        rejectVendor: function(index, vendorIndex) {
            let suggestion = this.vendorSuggestions[index];
            if (suggestion && suggestion.vendors) {
                suggestion.vendors.splice(vendorIndex, 1);
            }
        },

        getBadgeClass: function(dataSourceType) {
            const badges = {
                'api_synced':           'inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-green-500/10 text-green-600 border border-green-500/30',
                'contract_verified':    'inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-green-500/10 text-green-600 border border-green-500/30',
                'architect_confirmed':  'inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-blue-500/10 text-blue-600 border border-blue-500/30',
                'seeded':               'inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-gray-500/10 text-gray-600 border border-gray-500/30',
                'llm_proposed':         'inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-purple-500/10 text-purple-600 border border-purple-500/30'
            };
            return badges[dataSourceType] || badges['seeded'];
        },

        getBadgeLabel: function(dataSourceType) {
            const labels = {
                'api_synced':          'Live',
                'contract_verified':   'Verified',
                'architect_confirmed': 'Confirmed',
                'seeded':              'List Price',
                'llm_proposed':        'AI Estimate'
            };
            return labels[dataSourceType] || 'Unknown';
        },

        formatCost: function(cost) {
            if (!cost) return 'Contact sales';
            return '$' + Number(cost).toLocaleString() + '/yr';
        },

        // --- Inline correction ---
        editingPrice: null,  // {index, vendorIndex, value}

        startEditPrice: function(index, vendorIndex, currentCost) {
            this.editingPrice = {index: index, vendorIndex: vendorIndex, value: currentCost || ''};
        },

        cancelEditPrice: function() {
            this.editingPrice = null;
        },

        saveEditPrice: function(solutionId) {
            let self = this;
            const edit = self.editingPrice;
            if (!edit) return;
            const vendor = self.vendorSuggestions[edit.index].vendors[edit.vendorIndex];
            let csrf = document.querySelector('meta[name=csrf-token]');
            let headers = {'Content-Type': 'application/json'};
            if (csrf) headers['X-CSRFToken'] = csrf.content;

            fetch('/api/solutions/' + solutionId + '/suggestions/vendors/update-pricing', {
                method: 'POST',
                credentials: 'same-origin',
                headers: headers,
                body: JSON.stringify({pricing_id: vendor.pricing_id, annual_cost: parseFloat(edit.value)})
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                let payload = (data && data.data !== undefined) ? data.data : data;
                if (payload.success) {
                    vendor.annual_cost = payload.annual_cost;
                    vendor.data_source_type = 'architect_confirmed';
                    vendor.confirmed_by_count = payload.confirmed_by_count;
                }
                self.editingPrice = null;
            })
            .catch(function(err) {
                console.error('Price update error:', err);
                self.editingPrice = null;
            });
        },

        // --- Coverage voting ---
        voteCoverage: function(solutionId, mappingId, voteUp, index, vendorIndex) {
            let self = this;
            let csrf = document.querySelector('meta[name=csrf-token]');
            let headers = {'Content-Type': 'application/json'};
            if (csrf) headers['X-CSRFToken'] = csrf.content;

            fetch('/api/solutions/' + solutionId + '/suggestions/vendors/vote-coverage', {
                method: 'POST',
                credentials: 'same-origin',
                headers: headers,
                body: JSON.stringify({mapping_id: mappingId, vote_up: voteUp})
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                let payload = (data && data.data !== undefined) ? data.data : data;
                if (payload.success && self.vendorSuggestions[index] && self.vendorSuggestions[index].vendors[vendorIndex]) {
                    self.vendorSuggestions[index].vendors[vendorIndex].coverage_pct = payload.coverage_percentage;
                    self.vendorSuggestions[index].vendors[vendorIndex].confirmed_by_count = payload.confirmed_by_count;
                }
            })
            .catch(function(err) {
                console.error('Coverage vote error:', err);
            });
        },

        // Helper: extract capability IDs from the confirmed/accepted domain elements.
        // Called by journey_v2.js after domain confirmation to feed fetchVendorSuggestions.
        getConfirmedCapabilityIds: function() {
            const ids = [];
            let self = this;
            // From reasoning pipeline: reasoningCapabilities holds confirmed cap IDs
            if (self.reasoningCapabilities && self.reasoningCapabilities.length > 0) {
                self.reasoningCapabilities.forEach(function(c) {
                    if (c.capability_id) ids.push(c.capability_id);
                });
                return ids;
            }
            // From domain pipeline: acceptedCapabilities holds confirmed caps
            if (self.acceptedCapabilities && self.acceptedCapabilities.length > 0) {
                self.acceptedCapabilities.forEach(function(c) {
                    const id = c.id || c.existing_id;
                    if (id) ids.push(id);
                });
                return ids;
            }
            return ids;
        }
    };
}
