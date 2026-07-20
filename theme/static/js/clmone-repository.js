
/**
 * CLM One repository functionality
 * Provides advanced filtering, bulk selection, and details drawer
 */
class CLMOneRepository {
    constructor() {
        this.selectedContracts = new Set();
        this.contractCache = new Map();
        this.filters = {
            q: '',
            status: [],
            lifecycle_stage: [],
            contract_type: [],
            owner: [],
            counterparty: [],
            risk_level: [],
            approval_state: [],
            sort: 'updated_desc',
            page: 1,
            page_size: 25,
            expiring_within_days: null
        };
        this.currentUser = { role: 'admin' };
        this.columnVisibility = {
            type: true,
            counterparty: true,
            stage: true,
            owner: true,
            activity: false,
            key_date: true,
            value: true,
        };
        this.columnStorageKey = 'clmone-repo-columns-v2';
        
        this.init();
    }
    
    init() {
        this.loadColumnVisibility();
        this.setupEventListeners();
        this.setupKeyboardShortcuts();
        this.loadFromURL();
        this.syncControlsToFilters();
        this.syncSortHeaders();
        this.applyColumnVisibility();
        this.renderFilterChips();
        this.updateQuickFilterState();
        this.loadContracts();
    }
    
    setupEventListeners() {
        // Search input with debounce
        let searchTimeout;
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    this.filters.q = e.target.value;
                    this.filters.page = 1;
                    this.renderFilterChips();
                    this.loadContracts();
                    this.updateURL();
                }, 300);
            });
        }
        
        // Sort change (hidden select kept for URL/state sync)
        const sortSelect = document.getElementById('sort-select');
        if (sortSelect) {
            sortSelect.addEventListener('change', (e) => {
                this.applySort(e.target.value);
            });
        }

        document.querySelectorAll('.repo-sort-btn[data-sort]').forEach((button) => {
            button.addEventListener('click', () => this.toggleColumnSort(button.dataset.sort));
        });

        document.querySelectorAll('[data-status-filter]').forEach((button) => {
            button.addEventListener('click', () => this.applyStatusFilter(button.dataset.statusFilter || ''));
        });

        const filterToggle = document.getElementById('repo-filter-toggle');
        const filterDrawer = document.getElementById('repository-filters');
        if (filterToggle && filterDrawer) {
            filterToggle.addEventListener('click', () => {
                const open = filterDrawer.classList.toggle('is-open');
                filterToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            });
        }

        const colMenu = document.getElementById('repo-col-menu');
        const colToggle = document.getElementById('repo-col-toggle');
        if (colMenu && colToggle) {
            colToggle.addEventListener('click', () => {
                const open = colMenu.classList.toggle('is-open');
                colToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            });
            colMenu.querySelectorAll('[data-col-toggle]').forEach((input) => {
                input.addEventListener('change', () => {
                    const key = input.getAttribute('data-col-toggle');
                    if (!key || !(key in this.columnVisibility)) return;
                    this.columnVisibility[key] = input.checked;
                    this.persistColumnVisibility();
                    this.applyColumnVisibility();
                });
            });
        }

        document.addEventListener('click', (event) => {
            if (colMenu && colToggle && !colMenu.contains(event.target)) {
                colMenu.classList.remove('is-open');
                colToggle.setAttribute('aria-expanded', 'false');
            }
            if (!event.target.closest('.repo-row-menu')) {
                document.querySelectorAll('.repo-row-menu[open]').forEach((menu) => {
                    menu.open = false;
                });
            }
        });

        const bindSelectFilter = (id, apply) => {
            const control = document.getElementById(id);
            if (control) control.addEventListener('change', (event) => apply(event.target.value));
        };
        bindSelectFilter('status-filter-select', (value) => this.applyStatusFilter(value));
        bindSelectFilter('stage-filter-select', (value) => {
            this.filters.lifecycle_stage = value ? [value] : [];
            this.filters.page = 1;
            this.renderFilterChips(); this.updateURL(); this.loadContracts();
        });
        bindSelectFilter('type-filter-select', (value) => {
            this.filters.contract_type = value ? [value] : [];
            this.filters.page = 1;
            this.renderFilterChips(); this.updateURL(); this.loadContracts();
        });
        ['owner', 'counterparty', 'risk_level', 'approval_state'].forEach((filterName) => {
            bindSelectFilter(`${filterName.replace('_level', '').replace('_state', '')}-filter-select`, (value) => {
                this.filters[filterName] = value ? [value] : [];
                this.filters.page = 1;
                this.renderFilterChips(); this.updateURL(); this.loadContracts();
            });
        });
        bindSelectFilter('expiry-filter-select', (value) => {
            this.filters.expiring_within_days = value ? Number(value) : null;
            this.filters.page = 1;
            this.renderFilterChips(); this.updateQuickFilterState(); this.updateURL(); this.loadContracts();
        });

        document.querySelectorAll('[data-action="clear-repository-filters"]').forEach((button) => {
            button.addEventListener('click', () => this.clearRepositoryFilters());
        });

        // Select all checkbox
        const selectAllCheckbox = document.getElementById('select-all');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', (e) => {
                const checkboxes = document.querySelectorAll('.contract-checkbox');
                checkboxes.forEach(cb => {
                    cb.checked = e.target.checked;
                    if (e.target.checked) {
                        this.selectedContracts.add(cb.value);
                    } else {
                        this.selectedContracts.delete(cb.value);
                    }
                    const row = cb.closest('tr');
                    if (row) {
                        row.classList.toggle('wq-row-selected', e.target.checked);
                        row.setAttribute('aria-selected', String(e.target.checked));
                    }
                });
                this.updateBulkActionBar();
            });
        }

        const bulkStatusButton = document.getElementById('repo-bulk-status');
        if (bulkStatusButton) {
            bulkStatusButton.addEventListener('click', () => this.bulkChangeStatus());
        }

        // "Assign to Me" is disabled in the template (no assignment target
        // exists at the Contract level yet — see AssigneeChip's resolution
        // through Task/Approval/Deadline/WorkflowStep) — no click wiring
        // here, so there is no placeholder alert action.

        const bulkExportButton = document.getElementById('repo-bulk-export');
        if (bulkExportButton) {
            bulkExportButton.addEventListener('click', () => this.exportSelectedContracts());
        }

        document.querySelectorAll('[data-action="clear-selection"]').forEach((btn) => {
            btn.addEventListener('click', () => this.clearSelection());
        });
    }
    
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            if (e.key === '/' && !e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                const searchInput = document.getElementById('search-input');
                if (searchInput) searchInput.focus();
            }
            
            if (e.key === 'Escape') {
                this.closeDetailsDrawer();
                const filterDrawer = document.getElementById('repository-filters');
                const filterToggle = document.getElementById('repo-filter-toggle');
                if (filterDrawer) filterDrawer.classList.remove('is-open');
                if (filterToggle) filterToggle.setAttribute('aria-expanded', 'false');
                const colMenu = document.getElementById('repo-col-menu');
                const colToggle = document.getElementById('repo-col-toggle');
                if (colMenu) colMenu.classList.remove('is-open');
                if (colToggle) colToggle.setAttribute('aria-expanded', 'false');
            }
            
            if (e.key === 'n' && !e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                window.location.href = '/contracts/new/';
            }
        });
    }
    
    loadFromURL() {
        const params = new URLSearchParams(window.location.search);
        
        // Load filters from URL
        if (params.get('q')) this.filters.q = params.get('q');
        if (params.getAll('status').length) this.filters.status = params.getAll('status');
        if (params.getAll('lifecycle_stage').length) this.filters.lifecycle_stage = params.getAll('lifecycle_stage');
        if (params.getAll('contract_type').length) this.filters.contract_type = params.getAll('contract_type');
        ['owner', 'counterparty', 'risk_level', 'approval_state'].forEach((filterName) => {
            if (params.getAll(filterName).length) this.filters[filterName] = params.getAll(filterName);
        });
        if (params.get('sort')) this.filters.sort = params.get('sort');
        if (params.get('page')) this.filters.page = parseInt(params.get('page'));
        if (params.get('expiring_within_days')) this.filters.expiring_within_days = parseInt(params.get('expiring_within_days'));
        
        // Load contract detail if specified
        const contractId = params.get('contractId');
        if (contractId) {
            this.openDetailsDrawer(contractId);
        }
    }

    syncControlsToFilters() {
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.value = this.filters.q || '';
        }

        const sortSelect = document.getElementById('sort-select');
        if (sortSelect) {
            sortSelect.value = this.filters.sort;
        }
        this.syncSortHeaders();
        const statusSelect = document.getElementById('status-filter-select');
        if (statusSelect) statusSelect.value = this.filters.status.length === 1 ? this.filters.status[0] : '';
        const stageSelect = document.getElementById('stage-filter-select');
        if (stageSelect) stageSelect.value = this.filters.lifecycle_stage.length === 1 ? this.filters.lifecycle_stage[0] : '';
        const typeSelect = document.getElementById('type-filter-select');
        if (typeSelect) typeSelect.value = this.filters.contract_type.length === 1 ? this.filters.contract_type[0] : '';
        const ownerSelect = document.getElementById('owner-filter-select');
        if (ownerSelect) ownerSelect.value = this.filters.owner.length === 1 ? this.filters.owner[0] : '';
        const counterpartySelect = document.getElementById('counterparty-filter-select');
        if (counterpartySelect) counterpartySelect.value = this.filters.counterparty.length === 1 ? this.filters.counterparty[0] : '';
        const riskSelect = document.getElementById('risk-filter-select');
        if (riskSelect) riskSelect.value = this.filters.risk_level.length === 1 ? this.filters.risk_level[0] : '';
        const approvalSelect = document.getElementById('approval-filter-select');
        if (approvalSelect) approvalSelect.value = this.filters.approval_state.length === 1 ? this.filters.approval_state[0] : '';
        const expirySelect = document.getElementById('expiry-filter-select');
        if (expirySelect) expirySelect.value = this.filters.expiring_within_days ? String(this.filters.expiring_within_days) : '';
    }

    applyStatusFilter(status) {
        this.filters.status = status ? [status] : [];
        this.filters.expiring_within_days = null;
        this.filters.page = 1;
        this.renderFilterChips();
        this.updateQuickFilterState();
        this.updateURL();
        this.loadContracts();
    }

    applySort(sort) {
        this.filters.sort = sort || 'updated_desc';
        this.filters.page = 1;
        this.syncControlsToFilters();
        this.renderFilterChips();
        this.updateQuickFilterState();
        this.loadContracts();
        this.updateURL();
    }

    toggleColumnSort(column) {
        let next = 'updated_desc';
        if (column === 'title') {
            next = 'title';
        } else if (column === 'stage') {
            next = 'stage';
        } else if (column === 'status') {
            next = 'status';
        } else if (column === 'updated') {
            next = this.filters.sort === 'updated_desc' ? 'updated_asc' : 'updated_desc';
        }
        this.applySort(next);
    }

    syncSortHeaders() {
        const table = document.getElementById('contracts-table');
        if (!table) return;
        const sort = this.filters.sort || 'updated_desc';
        const mapping = {
            title: { key: 'title', direction: 'ascending' },
            stage: { key: 'stage', direction: 'ascending' },
            status: { key: 'status', direction: 'ascending' },
            updated_desc: { key: 'updated', direction: 'descending' },
            updated_asc: { key: 'updated', direction: 'ascending' },
        };
        const active = mapping[sort] || mapping.updated_desc;
        if (window.CLMOne && window.CLMOne.dataTable && typeof window.CLMOne.dataTable.setSort === 'function') {
            window.CLMOne.dataTable.setSort(table, active.key, active.direction);
            return;
        }
        table.querySelectorAll('[data-column-key]').forEach((header) => {
            const isActive = header.getAttribute('data-column-key') === active.key;
            header.setAttribute('aria-sort', isActive ? active.direction : 'none');
        });
    }

    loadColumnVisibility() {
        try {
            const raw = window.localStorage.getItem(this.columnStorageKey);
            if (!raw) return;
            const parsed = JSON.parse(raw);
            Object.keys(this.columnVisibility).forEach((key) => {
                if (typeof parsed[key] === 'boolean') this.columnVisibility[key] = parsed[key];
            });
        } catch (error) {
            // Ignore storage failures and keep defaults.
        }
        document.querySelectorAll('[data-col-toggle]').forEach((input) => {
            const key = input.getAttribute('data-col-toggle');
            if (key && key in this.columnVisibility) input.checked = this.columnVisibility[key];
        });
    }

    persistColumnVisibility() {
        try {
            window.localStorage.setItem(this.columnStorageKey, JSON.stringify(this.columnVisibility));
        } catch (error) {
            // Ignore storage failures.
        }
    }

    applyColumnVisibility() {
        Object.entries(this.columnVisibility).forEach(([key, visible]) => {
            document.querySelectorAll(`[data-col="${key}"]`).forEach((cell) => {
                cell.classList.toggle('is-hidden', !visible);
            });
        });
    }

    updateQuickFilterState() {
        const activeStatus = this.filters.status.length === 1 ? this.filters.status[0] : '';
        document.querySelectorAll('[data-status-filter]').forEach((button) => {
            const isActive = !this.filters.expiring_within_days && (button.dataset.statusFilter || '') === activeStatus;
            button.classList.toggle('chip-active', isActive);
            button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        });
    }

    updateURL() {
        const params = new URLSearchParams();
        
        if (this.filters.q) params.set('q', this.filters.q);
        this.filters.status.forEach(s => params.append('status', s));
        this.filters.lifecycle_stage.forEach(s => params.append('lifecycle_stage', s));
        this.filters.contract_type.forEach(t => params.append('contract_type', t));
        ['owner', 'counterparty', 'risk_level', 'approval_state'].forEach((filterName) => {
            this.filters[filterName].forEach((value) => params.append(filterName, value));
        });
        if (this.filters.sort !== 'updated_desc') params.set('sort', this.filters.sort);
        if (this.filters.page !== 1) params.set('page', this.filters.page.toString());
        if (this.filters.expiring_within_days) params.set('expiring_within_days', this.filters.expiring_within_days.toString());

        const newURL = window.location.pathname + '?' + params.toString();
        window.history.replaceState({}, '', newURL);
    }
    
    async loadContracts() {
        this.showLoading();
        
        try {
            const params = new URLSearchParams();
            if (this.filters.q) params.set('q', this.filters.q);
            this.filters.status.forEach(s => params.append('status', s));
            this.filters.lifecycle_stage.forEach(s => params.append('lifecycle_stage', s));
            this.filters.contract_type.forEach(t => params.append('contract_type', t));
            ['owner', 'counterparty', 'risk_level', 'approval_state'].forEach((filterName) => {
                this.filters[filterName].forEach((value) => params.append(filterName, value));
            });
            params.set('sort', this.filters.sort);
            params.set('page', this.filters.page.toString());
            params.set('page_size', this.filters.page_size.toString());
            if (this.filters.expiring_within_days) params.set('expiring_within_days', this.filters.expiring_within_days.toString());

            const response = await fetch(`/contracts/api/contracts/?${params.toString()}`);
            const result = await response.json();
            
            if (response.ok) {
                (result.contracts || []).forEach((contract) => {
                    this.contractCache.set(String(contract.id), contract);
                });
                this.renderContracts(result);
                this.updatePagination(result);
            } else {
                this.showError(result.error || 'Failed to load contracts');
            }
        } catch (error) {
            this.showError('Network error: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }
    
    escapeHtml(value) {
        const div = document.createElement('div');
        div.textContent = value === null || value === undefined ? '' : String(value);
        return div.innerHTML;
    }

    // Same markup/CSS contract as components/_stage_dots.html — a
    // JS-side renderer, not a competing visual, so Repository rows look
    // identical to Dashboard queue rows.
    renderStageDots(steps) {
        if (!steps || !steps.length) return '<span class="c-dim">—</span>';
        const current = steps.find((s) => s.state === 'current')
            || [...steps].reverse().find((s) => s.state === 'done');
        const label = current ? current.label : 'Not started';
        const dots = steps.map((s) => `<i class="stage-dot stage-dot-${s.state}" aria-hidden="true"></i>`).join('');
        return `<span class="stage-dots" title="${this.escapeHtml(label)}"><span class="sr-only">${this.escapeHtml(label)}</span>${dots}</span>`;
    }

    // Same markup/CSS contract as components/_assignee_chip.html.
    renderAssigneeChip(name, initial) {
        if (!name) {
            return '<span class="assignee-chip assignee-chip-empty"><span class="assignee-chip-avatar assignee-chip-avatar-empty" aria-hidden="true"></span><span class="assignee-chip-name repo-empty-label">Unassigned</span></span>';
        }
        const shownInitial = initial || name.slice(0, 1).toUpperCase();
        return `<span class="assignee-chip"><span class="assignee-chip-avatar avatar-gradient-bg">${this.escapeHtml(shownInitial)}</span><span class="assignee-chip-name">${this.escapeHtml(name)}</span></span>`;
    }

    // Same markup/CSS contract as components/_activity_line.html.
    renderActivityLine(text, time, initial) {
        if (!text) return '<span class="repo-empty-label">No recent activity</span>';
        const shownInitial = initial || 'S';
        const full = String(text).trim();
        const tokens = full.split(/\s+/);
        let body = this.escapeHtml(full);
        // activity_line_parts always builds "{actor} {verb} {object}" — keep
        // actor + verb visible and let the trailing object ellipsize first.
        if (tokens.length >= 3) {
            const objectLabel = tokens.pop();
            const verb = tokens.pop();
            const actor = tokens.join(' ');
            body = `<span class="activity-line-actor">${this.escapeHtml(actor)}</span>`
                + `<span class="activity-line-action"> ${this.escapeHtml(verb)} ${this.escapeHtml(objectLabel)}</span>`;
        }
        return `<div class="activity-line"><span class="activity-line-avatar avatar-gradient-bg">${this.escapeHtml(shownInitial)}</span><div class="activity-line-body"><div class="activity-line-desc" title="${this.escapeHtml(full)}">${body}</div><div class="activity-line-time">${this.escapeHtml(time || '')}</div></div></div>`;
    }

    renderStatusMeta(contract) {
        const status = this.escapeHtml(contract.status_display || contract.status || '');
        if (contract.has_exception) {
            return `<span class="dc-ds-badge dc-ds-badge--sm dc-ds-badge--attention repo-exception-badge">Exception</span><span class="repo-status-sep" aria-hidden="true">·</span><span class="text-sm repo-muted-text">${status}</span>`;
        }
        return `<span class="text-sm repo-muted-text">${status}</span>`;
    }

    renderStageBadge(contract) {
        const shortLabel = contract.stage_display || 'Drafting';
        const fullLabel = contract.stage_display_full || shortLabel;
        const titleAttr = fullLabel !== shortLabel ? ` title="${this.escapeHtml(fullLabel)}"` : ` title="${this.escapeHtml(fullLabel)}"`;
        return `<span class="dc-ds-badge dc-ds-badge--sm dc-ds-badge--${contract.stage_badge_tone || 'neutral'} repo-stage-badge"${titleAttr}>${this.escapeHtml(shortLabel)}</span>`;
    }

    renderRowActions(contract) {
        const title = this.escapeHtml(contract.title);
        const detailUrl = `/contracts/${contract.id}/`;
        const activityUrl = `${detailUrl}?tab=activity`;
        return `
            <details class="wq-kebab repo-row-menu">
              <summary aria-label="Actions for ${title}" class="wq-kebab-trigger">
                <svg aria-hidden="true" fill="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="5" r="1.7"></circle><circle cx="12" cy="12" r="1.7"></circle><circle cx="12" cy="19" r="1.7"></circle></svg>
              </summary>
              <div class="wq-kebab-menu">
                <a href="${detailUrl}">Open contract</a>
                <a href="${activityUrl}">View activity</a>
              </div>
            </details>
        `;
    }

    renderTypeCell(contract) {
        const shortLabel = contract.contract_type_short || contract.contract_type_display || 'Other';
        const fullLabel = contract.contract_type_display || shortLabel;
        return `<span class="repo-type-label dc-ds-table-cell-text" title="${this.escapeHtml(fullLabel)}">${this.escapeHtml(shortLabel)}</span>`;
    }

    renderTruncatedText(value, fallback = '—') {
        const text = (value || '').trim() || fallback;
        if (text === '—') {
            return '<span class="repo-empty-label">—</span>';
        }
        return `<span class="dc-ds-table-cell-text" title="${this.escapeHtml(text)}">${this.escapeHtml(text)}</span>`;
    }

    renderContracts(result) {
        const tbody = document.getElementById('contracts-tbody');
        if (!tbody) return;

        if (result.contracts.length === 0) {
            const hasActiveFilters = Boolean(
                this.filters.q
                || this.filters.status.length
                || this.filters.lifecycle_stage.length
                || this.filters.contract_type.length
                || this.filters.owner.length
                || this.filters.counterparty.length
                || this.filters.risk_level.length
                || this.filters.approval_state.length
                || this.filters.expiring_within_days
            );
            tbody.innerHTML = `
                <tr><td colspan="10">
                    <div class="dc-ds-empty dc-ds-empty--compact repo-empty-state">
                        <h2 class="dc-ds-empty__title">${hasActiveFilters ? 'No contracts match this view' : 'Your repository is ready'}</h2>
                        <p class="dc-ds-empty__copy">${hasActiveFilters
                            ? 'The current search or filters exclude every contract in this workspace.'
                            : 'No governed agreements have been added to this workspace yet.'}</p>
                        <p class="dc-ds-empty__how">${hasActiveFilters
                            ? 'Contracts appear here as soon as they match the selected criteria.'
                            : 'Uploaded agreements and governed drafts appear here automatically with their stage, owner, activity, and key dates.'}</p>
                        <div class="dc-ds-actions dc-ds-empty__actions">
                            ${hasActiveFilters
                                ? '<button type="button" class="dc-ds-button dc-ds-button--primary" data-action="clear-repository-filters">Clear filters</button>'
                            : '<a href="/contracts/new/" class="dc-ds-button dc-ds-button--primary">Start new contract</a>'}
                        </div>
                    </div>
                </td></tr>
            `;
            const clearFiltersButton = tbody.querySelector('[data-action="clear-repository-filters"]');
            if (clearFiltersButton) {
                clearFiltersButton.addEventListener('click', () => this.clearRepositoryFilters());
            }
            this.updateResultCount(0);
            return;
        }

        tbody.innerHTML = result.contracts.map(contract => `
            <tr class="contract-row cursor-pointer" data-contract-id="${contract.id}" aria-selected="false">
                <td class="repo-cell" data-col="select">
                    <input type="checkbox" class="contract-checkbox" value="${contract.id}" aria-label="Select ${this.escapeHtml(contract.title)}">
                </td>
                <td class="repo-cell" data-col="title">
                    <div class="repo-title-stack">
                      <div class="font-medium repo-contract-title">${this.escapeHtml(contract.title)}</div>
                      <div class="repo-title-meta">${this.renderStatusMeta(contract)}</div>
                    </div>
                </td>
                <td class="repo-cell" data-col="type">
                    ${this.renderTypeCell(contract)}
                </td>
                <td class="repo-cell" data-col="counterparty">
                    ${this.renderTruncatedText(contract.counterparty)}
                </td>
                <td class="repo-cell" data-col="stage">
                    ${this.renderStageBadge(contract)}
                </td>
                <td class="repo-cell" data-col="owner">
                    ${this.renderAssigneeChip(contract.assignee_name, contract.assignee_initial)}
                </td>
                <td class="repo-cell" data-col="activity">
                    ${this.renderActivityLine(contract.latest_activity_text, contract.latest_activity_time, contract.latest_activity_initial)}
                </td>
                <td class="repo-cell repo-key-date${contract.due_overdue ? ' wq-due-overdue' : ''}" data-col="key_date">
                    ${contract.end_date_display ? this.escapeHtml(contract.end_date_display) : '<span class="repo-empty-label">—</span>'}
                </td>
                <td class="repo-cell repo-value" data-col="value">
                    ${contract.value_display || '—'}
                </td>
                <td class="repo-cell repo-actions-cell" data-col="actions">
                    ${this.renderRowActions(contract)}
                </td>
            </tr>
        `).join('');
        
        // Add click handlers
        tbody.querySelectorAll('.contract-row').forEach(row => {
            row.addEventListener('click', (e) => {
                if (!e.target.closest('input, a, button, summary, .wq-kebab, .wq-kebab-menu')) {
                    const contractId = row.dataset.contractId;
                    window.location.href = `/contracts/${contractId}/`;
                }
            });
        });

        tbody.querySelectorAll('.repo-row-menu').forEach((menu) => {
            menu.addEventListener('click', (event) => event.stopPropagation());
            menu.addEventListener('toggle', () => {
                if (!menu.open) return;
                tbody.querySelectorAll('.repo-row-menu[open]').forEach((other) => {
                    if (other !== menu) other.open = false;
                });
            });
        });
        if (window.CLMOneRowMenus && typeof window.CLMOneRowMenus.init === 'function') {
            window.CLMOneRowMenus.init(tbody);
        }
        // Add checkbox handlers
        tbody.querySelectorAll('.contract-checkbox').forEach(cb => {
            cb.addEventListener('change', (e) => {
                if (e.target.checked) {
                    this.selectedContracts.add(e.target.value);
                } else {
                    this.selectedContracts.delete(e.target.value);
                }
                // Keep the row visibly selected even after the pointer
                // moves away — a checked checkbox alone is easy to lose
                // track of in a dense table.
                const row = e.target.closest('tr');
                if (row) row.classList.toggle('wq-row-selected', e.target.checked);
                if (row) row.setAttribute('aria-selected', String(e.target.checked));
                this.updateBulkActionBar();
            });
        });

        this.applyColumnVisibility();
        this.updateResultCount(Number(result?.total_count || result.contracts.length));
    }
    
    updateBulkActionBar() {
        const count = this.selectedContracts.size;
        const bulkBar = document.getElementById('bulk-action-bar');
        
        if (count > 0) {
            if (bulkBar) {
                bulkBar.style.display = 'flex';
                bulkBar.querySelector('#selected-count').textContent = `${count} selected`;
            }
        } else {
            if (bulkBar) bulkBar.style.display = 'none';
        }
    }

    clearSelection() {
        this.selectedContracts.clear();

        const selectAllCheckbox = document.getElementById('select-all');
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
        }

        document.querySelectorAll('.contract-checkbox').forEach(cb => {
            cb.checked = false;
            const row = cb.closest('tr');
            if (row) row.classList.remove('wq-row-selected');
            if (row) row.setAttribute('aria-selected', 'false');
        });

        this.updateBulkActionBar();
    }

    clearRepositoryFilters() {
        this.filters.q = '';
        this.filters.status = [];
        this.filters.lifecycle_stage = [];
        this.filters.contract_type = [];
        this.filters.owner = [];
        this.filters.counterparty = [];
        this.filters.risk_level = [];
        this.filters.approval_state = [];
        this.filters.expiring_within_days = null;
        this.filters.page = 1;
        this.syncControlsToFilters();
        this.renderFilterChips();
        this.updateQuickFilterState();
        this.updateURL();
        this.loadContracts();
    }

    updateResultCount(totalCount) {
        const countEl = document.getElementById('repo-result-count');
        if (!countEl) return;
        const count = Number(totalCount || 0);
        countEl.textContent = `${count} contract${count === 1 ? '' : 's'}`;
    }

    updatePagination(result) {
        const container = document.getElementById('pagination-container');
        if (!container) return;

        const currentPage = Number(result?.page || 1);
        const totalPages = Number(result?.total_pages || 1);
        const totalCount = Number(result?.total_count || 0);
        this.updateResultCount(totalCount);

        if (totalPages <= 1) {
            container.innerHTML = '';
            return;
        }

        const prevDisabled = currentPage <= 1;
        const nextDisabled = currentPage >= totalPages;

        container.innerHTML = `
            <div class="dc-ds-table-pagination">
                <div class="text-sm repo-muted-text">
                    Page ${currentPage} of ${totalPages}
                </div>
                <div class="dc-ds-table-pagination__actions">
                    <button id="repo-page-prev" type="button" class="repo-mini-btn" aria-label="Previous page" ${prevDisabled ? 'disabled' : ''}>Previous</button>
                    <button id="repo-page-next" type="button" class="repo-mini-btn" aria-label="Next page" ${nextDisabled ? 'disabled' : ''}>Next</button>
                </div>
            </div>
        `;

        const prevBtn = document.getElementById('repo-page-prev');
        const nextBtn = document.getElementById('repo-page-next');

        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                if (this.filters.page <= 1) return;
                this.filters.page -= 1;
                this.updateURL();
                this.loadContracts();
            });
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                if (this.filters.page >= totalPages) return;
                this.filters.page += 1;
                this.updateURL();
                this.loadContracts();
            });
        }
    }
    
    async openDetailsDrawer(contractId) {
        const drawer = document.getElementById('details-drawer');
        if (!drawer) return;
        
        // Update URL
        const params = new URLSearchParams(window.location.search);
        params.set('contractId', contractId);
        window.history.replaceState({}, '', '?' + params.toString());
        
        // Show loading state
        drawer.innerHTML = '<div class="p-6">Loading...</div>';
        drawer.classList.add('active');
        
        try {
            const response = await fetch(`/contracts/api/contracts/${contractId}/`);
            const contract = await response.json();
            
            if (response.ok) {
                this.renderContractDetails(contract, drawer);
            } else {
                drawer.innerHTML = '<div class="p-6 text-danger">Failed to load contract details</div>';
            }
        } catch (error) {
            drawer.innerHTML = '<div class="p-6 text-danger">Network error</div>';
        }
    }
    
    renderContractDetails(contract, drawer) {
        drawer.innerHTML = `
            <div class="p-6">
                <div class="flex items-center justify-between mb-4">
                    <h2 class="text-xl font-semibold">${this.escapeHtml(contract.title)}</h2>
                    <button onclick="window.clmoneRepository.closeDetailsDrawer()" class="btn-ghost">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>

                <div class="space-y-4">
                    <div>
                        <label class="text-sm text-muted">Status</label>
                        <div><span class="dc-ds-badge dc-ds-badge--sm dc-ds-badge--${contract.status_badge_tone || 'neutral'}">${this.escapeHtml(contract.status_display || contract.status)}</span></div>
                    </div>

                    <div>
                        <label class="text-sm text-muted">Assigned to</label>
                        <div>${this.renderAssigneeChip(contract.assignee_name, contract.assignee_initial)}</div>
                    </div>

                    <div>
                        <label class="text-sm text-muted">Counterparty</label>
                        <div>${this.escapeHtml(contract.counterparty || '-')}</div>
                    </div>

                    <div>
                        <label class="text-sm text-muted">Value</label>
                        <div>${contract.value_display || '-'}</div>
                    </div>

                    <div>
                        <label class="text-sm text-muted">Owner</label>
                        <div>${this.escapeHtml(contract.owner)}</div>
                    </div>

                    <div>
                        <label class="text-sm text-muted">Content</label>
                        <div class="mt-1 p-3 bg-hover rounded text-sm">${this.escapeHtml(contract.content || 'No content')}</div>
                    </div>
                </div>

                <div class="mt-6 pt-4 border-t">
                    <a href="/contracts/${contract.id}/" class="btn-primary">Open contract</a>
                </div>
            </div>
        `;
    }
    
    closeDetailsDrawer() {
        const drawer = document.getElementById('details-drawer');
        if (drawer) drawer.classList.remove('active');
        
        // Remove contractId from URL
        const params = new URLSearchParams(window.location.search);
        params.delete('contractId');
        window.history.replaceState({}, '', '?' + params.toString());
    }

    filterDisplayValue(filterName, value) {
        const controlIds = {
            status: 'status-filter-select',
            lifecycle_stage: 'stage-filter-select',
            contract_type: 'type-filter-select',
            owner: 'owner-filter-select',
            counterparty: 'counterparty-filter-select',
            risk_level: 'risk-filter-select',
            approval_state: 'approval-filter-select',
        };
        const control = document.getElementById(controlIds[filterName]);
        const option = control && Array.from(control.options).find((entry) => entry.value === value);
        return option ? option.textContent.trim() : value;
    }
    
    renderFilterChips() {
        const container = document.getElementById('filter-chips');
        if (!container) return;

        const chips = [];
        if (this.filters.q) {
            chips.push({
                label: `Search: ${this.filters.q}`,
                onClick: () => {
                    this.filters.q = '';
                    this.filters.page = 1;
                    this.syncControlsToFilters();
                    this.renderFilterChips();
                    this.updateQuickFilterState();
                    this.updateURL();
                    this.loadContracts();
                }
            });
        }

        if (this.filters.expiring_within_days) {
            chips.push({
                label: `Expiring within ${this.filters.expiring_within_days}d`,
                onClick: () => {
                    this.filters.expiring_within_days = null;
                    this.filters.page = 1;
                    this.renderFilterChips();
                    this.updateQuickFilterState();
                    this.updateURL();
                    this.loadContracts();
                }
            });
        }

        this.filters.status.forEach((status) => {
            chips.push({
                label: `Status: ${this.filterDisplayValue('status', status)}`,
                onClick: () => {
                    this.filters.status = this.filters.status.filter((value) => value !== status);
                    this.filters.page = 1;
                    this.renderFilterChips();
                    this.syncControlsToFilters();
                    this.updateQuickFilterState();
                    this.updateURL();
                    this.loadContracts();
                }
            });
        });

        this.filters.lifecycle_stage.forEach((stage) => {
            chips.push({
                label: `Stage: ${this.filterDisplayValue('lifecycle_stage', stage)}`,
                onClick: () => {
                    this.filters.lifecycle_stage = this.filters.lifecycle_stage.filter((value) => value !== stage);
                    this.filters.page = 1;
                    this.renderFilterChips();
                    this.syncControlsToFilters();
                    this.updateURL();
                    this.loadContracts();
                }
            });
        });

        if (this.filters.sort && this.filters.sort !== 'updated_desc') {
            chips.push({
                label: `Sort: ${this.filters.sort}`,
                onClick: () => {
                    this.filters.sort = 'updated_desc';
                    this.filters.page = 1;
                    this.syncControlsToFilters();
                    this.renderFilterChips();
                    this.updateQuickFilterState();
                    this.updateURL();
                    this.loadContracts();
                }
            });
        }

        this.filters.contract_type.forEach((contractType) => {
            chips.push({
                label: `Type: ${this.filterDisplayValue('contract_type', contractType)}`,
                onClick: () => {
                    this.filters.contract_type = this.filters.contract_type.filter((value) => value !== contractType);
                    this.filters.page = 1;
                    this.renderFilterChips();
                    this.updateURL();
                    this.loadContracts();
                }
            });
        });

        const filterLabels = {
            owner: 'Owner',
            counterparty: 'Counterparty',
            risk_level: 'Risk',
            approval_state: 'Approval',
        };
        Object.entries(filterLabels).forEach(([filterName, label]) => {
            this.filters[filterName].forEach((value) => {
                chips.push({
                    label: `${label}: ${this.filterDisplayValue(filterName, value)}`,
                    onClick: () => {
                        this.filters[filterName] = this.filters[filterName].filter((entry) => entry !== value);
                        this.filters.page = 1;
                        this.syncControlsToFilters();
                        this.renderFilterChips();
                        this.updateURL();
                        this.loadContracts();
                    }
                });
            });
        });

        if (chips.length === 0) {
            container.innerHTML = '';
            container.hidden = true;
            return;
        }

        container.hidden = false;
        container.innerHTML = `
            <div class="flex items-center gap-2 flex-wrap">
                ${chips.map((chip) => `
                    <button type="button" class="repo-filter-chip dc-ds-choice is-selected" data-chip-label="${chip.label}" aria-pressed="true">
                        ${chip.label}
                        <span aria-hidden="true">×</span>
                    </button>
                `).join('')}
            </div>
        `;

        container.querySelectorAll('[data-chip-label]').forEach((button) => {
            const chip = chips.find((entry) => entry.label === button.dataset.chipLabel);
            if (chip) {
                button.addEventListener('click', chip.onClick);
            }
        });
    }
    
    showLoading() {
        const table = document.getElementById('contracts-table');
        const tbody = document.getElementById('contracts-tbody');
        if (table) {
            table.classList.add('loading');
            table.setAttribute('data-loading', 'true');
            table.setAttribute('aria-busy', 'true');
        }
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="10"><div class="dc-ds-table-state" role="status" aria-live="polite">Loading contracts…</div></td></tr>';
        }
    }
    
    hideLoading() {
        const table = document.getElementById('contracts-table');
        if (table) {
            table.classList.remove('loading');
            table.removeAttribute('data-loading');
            table.removeAttribute('aria-busy');
        }
    }
    
    showError(message) {
        console.error('Repository error:', message);
        const tbody = document.getElementById('contracts-tbody');
        if (tbody) {
            tbody.innerHTML = `
                <tr><td colspan="10">
                    <div class="dc-ds-empty dc-ds-empty--compact repo-empty-state">
                        <h2 class="dc-ds-empty__title">Repository data could not be loaded</h2>
                        <p class="dc-ds-empty__copy">The contract service did not return a usable response.</p>
                        <p class="dc-ds-empty__how">Your existing contracts are unchanged and will appear when the connection recovers.</p>
                        <div class="dc-ds-actions dc-ds-empty__actions">
                            <button type="button" class="dc-ds-button dc-ds-button--primary" data-action="retry-repository">Try again</button>
                        </div>
                    </div>
                </td></tr>
            `;
            tbody.querySelector('[data-action="retry-repository"]')
                ?.addEventListener('click', () => this.loadContracts());
        }
        if (window.CLMOne && typeof window.CLMOne.toast === 'function') {
            window.CLMOne.toast(message, { tone: 'danger' });
        }
    }
    
    async bulkChangeStatus() {
        if (!this.selectedContracts.size) {
            window.alert('Select one or more contracts first.');
            return;
        }

        const nextStatus = window.prompt(
            'Enter the new status (DRAFT, PENDING, IN_REVIEW, APPROVED, ACTIVE, EXPIRED, TERMINATED, COMPLETED, CANCELLED)',
            'ACTIVE'
        );
        if (!nextStatus) return;

        const normalizedStatus = nextStatus.trim().toUpperCase();
        const allowedStatuses = new Set(['DRAFT', 'PENDING', 'IN_REVIEW', 'APPROVED', 'ACTIVE', 'EXPIRED', 'TERMINATED', 'COMPLETED', 'CANCELLED']);
        if (!allowedStatuses.has(normalizedStatus)) {
            window.alert('That is not a valid contract status.');
            return;
        }

        const response = await fetch('/contracts/api/contracts/bulk-update/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken(),
            },
            body: JSON.stringify({
                contract_ids: Array.from(this.selectedContracts),
                updates: { status: normalizedStatus },
            }),
        });

        const payload = await response.json();
        if (!response.ok) {
            window.alert(payload.error || 'Bulk status update failed.');
            return;
        }

        this.loadContracts();
    }

    exportSelectedContracts() {
        if (!this.selectedContracts.size) {
            window.alert('Select one or more contracts first.');
            return;
        }

        const rows = Array.from(this.selectedContracts)
            .map((contractId) => this.contractCache.get(String(contractId)))
            .filter(Boolean);

        if (!rows.length) {
            window.alert('Selected contracts are not loaded in the current view.');
            return;
        }

        const header = ['id', 'title', 'status', 'stage', 'document_state', 'counterparty', 'value', 'owner', 'updated_at'];
        const csvLines = [
            header.join(','),
            ...rows.map((contract) => [
                contract.id,
                this.csvEscape(contract.title),
                this.csvEscape(contract.status_display || contract.status),
                this.csvEscape(contract.stage_display_full || contract.stage_display || ''),
                this.csvEscape(contract.document_state_display || contract.document_state || ''),
                this.csvEscape(contract.counterparty || ''),
                contract.value ?? '',
                this.csvEscape(contract.owner || ''),
                this.csvEscape(contract.updated_at || ''),
            ].join(',')),
        ];

        const blob = new Blob([csvLines.join('\n')], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'repository-contracts.csv';
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    }

    csvEscape(value) {
        const text = String(value ?? '');
        if (text.includes(',') || text.includes('"') || text.includes('\n')) {
            return `"${text.replaceAll('"', '""')}"`;
        }
        return text;
    }

    getCsrfToken() {
        const cookieName = 'csrftoken';
        return document.cookie
            .split('; ')
            .find((row) => row.startsWith(`${cookieName}=`))
            ?.split('=')[1] || '';
    }
}

// Initialize when DOM is loaded and CLM One mode is enabled
document.addEventListener('DOMContentLoaded', () => {
    if (window.location.pathname.includes('/repository')) {
        window.clmoneRepository = new CLMOneRepository();
    }
});
