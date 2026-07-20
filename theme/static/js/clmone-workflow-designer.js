/**
 * Workflow Designer canvas: selection, inspector, rules, DnD, zoom, validation, autosave.
 */
(function () {
  const ZOOM_MIN = 0.6;
  const ZOOM_MAX = 1.6;
  const ZOOM_STEP = 0.1;

  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  function csrfToken() {
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input) return input.value;
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  function setStatus(root, text, tone) {
    const el = root.querySelector('[data-save-status]');
    if (!el) return;
    el.textContent = text;
    el.dataset.tone = tone || 'neutral';
  }

  function setDirty(root, dirty) {
    const saveBtn = root.querySelector('[data-save-changes]');
    if (saveBtn) {
      saveBtn.disabled = !dirty;
      saveBtn.hidden = !dirty;
    }
    if (dirty) setStatus(root, 'Unsaved changes', 'attention');
  }

  function storageKey(root, suffix) {
    return `wf-designer:${root.dataset.templateId || 'x'}:${suffix}`;
  }

  function persistCanvas(root, api) {
    if (!api) return;
    const viewport = root.querySelector('[data-canvas-viewport]');
    try {
      sessionStorage.setItem(storageKey(root, 'zoom'), String(api.getZoom()));
      if (viewport) {
        sessionStorage.setItem(storageKey(root, 'scroll'), JSON.stringify({
          left: viewport.scrollLeft,
          top: viewport.scrollTop,
        }));
      }
    } catch (err) {
      /* ignore quota / private mode */
    }
  }

  function restoreCanvas(root, api) {
    if (!api) return;
    const viewport = root.querySelector('[data-canvas-viewport]');
    try {
      const zoom = Number(sessionStorage.getItem(storageKey(root, 'zoom')));
      if (zoom) api.setZoom(zoom);
      const scroll = JSON.parse(sessionStorage.getItem(storageKey(root, 'scroll') || 'null'));
      if (viewport && scroll) {
        viewport.scrollLeft = scroll.left || 0;
        viewport.scrollTop = scroll.top || 0;
      }
    } catch (err) {
      /* ignore */
    }
  }

  function centreStep(root, stepId) {
    const card = root.querySelector(`[data-step-id="${stepId}"]`);
    const viewport = root.querySelector('[data-canvas-viewport]');
    if (!card || !viewport) return;
    const cardRect = card.getBoundingClientRect();
    const viewRect = viewport.getBoundingClientRect();
    const deltaX = cardRect.left + cardRect.width / 2 - (viewRect.left + viewRect.width / 2);
    const deltaY = cardRect.top + cardRect.height / 2 - (viewRect.top + viewRect.height / 2);
    viewport.scrollLeft += deltaX;
    viewport.scrollTop += deltaY;
  }

  function openInspectorSection(root, field) {
    const map = {
      assignment: 'assignment',
      sla_hours: 'timing',
      escalation_after_hours: 'timing',
      conditions: 'conditions',
    };
    const sectionKey = map[field] || 'basics';
    const section = root.querySelector(`[data-section="${sectionKey}"]`);
    if (section && !section.open) section.open = true;
    const focusMap = {
      assignment: '#id_assignee_role, [name="assignee_role"]',
      sla_hours: '#id_sla_hours, [name="sla_hours"]',
      escalation_after_hours: '#id_escalation_after_hours, [name="escalation_after_hours"]',
      conditions: '[data-add-clause], [data-rule-field]',
    };
    const selector = focusMap[field];
    if (!selector) return;
    const target = root.querySelector(selector);
    if (target) target.focus();
  }

  function syncScenarioSave(root) {
    const form = root.querySelector('[data-test-form]');
    const saveBtn = root.querySelector('[data-save-scenario]');
    const hint = root.querySelector('[data-save-hint]');
    const ran = form?.querySelector('[data-scenario-ran]');
    const nameField = form?.querySelector('[name="scenario_name"]');
    if (!saveBtn) return;
    const hasName = Boolean((nameField?.value || '').trim());
    const hasRun = ran?.value === '1';
    const canSave = hasRun && hasName;
    saveBtn.disabled = !canSave;
    if (hint) {
      if (!hasRun) {
        hint.textContent = 'Save is available after you run a scenario with a scenario name.';
      } else if (!hasName) {
        hint.textContent = 'Provide a scenario name to save this run.';
      } else {
        hint.textContent = 'Ready to save this simulation for reuse.';
      }
    }
  }

  function bindMultiselect(root) {
    root.querySelectorAll('[data-multiselect]').forEach((wrap) => {
      const toggle = wrap.querySelector('[data-multiselect-toggle]');
      const panel = wrap.querySelector('[data-multiselect-panel]');
      const search = wrap.querySelector('[data-multiselect-search]');
      const chips = wrap.querySelector('[data-multiselect-chips]');
      const summary = wrap.querySelector('[data-multiselect-summary]');
      const options = () => Array.from(wrap.querySelectorAll('[data-multiselect-option]'));

      const refresh = () => {
        const selected = options().filter((input) => input.checked);
        if (summary) {
          summary.textContent = selected.length
            ? `${selected.length} selected`
            : 'All event types';
        }
        if (chips) {
          chips.innerHTML = '';
          selected.forEach((input) => {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'wf-multiselect__chip';
            chip.textContent = `${input.dataset.label || input.value} ×`;
            chip.addEventListener('click', () => {
              input.checked = false;
              refresh();
            });
            chips.appendChild(chip);
          });
        }
      };

      toggle?.addEventListener('click', () => {
        const open = panel?.hasAttribute('hidden');
        if (!panel) return;
        if (open) {
          panel.removeAttribute('hidden');
          toggle.setAttribute('aria-expanded', 'true');
          search?.focus();
        } else {
          panel.setAttribute('hidden', '');
          toggle.setAttribute('aria-expanded', 'false');
        }
      });

      search?.addEventListener('input', () => {
        const needle = (search.value || '').trim().toLowerCase();
        options().forEach((input) => {
          const label = (input.dataset.label || input.value || '').toLowerCase();
          const row = input.closest('li');
          if (row) row.hidden = Boolean(needle) && !label.includes(needle);
        });
      });

      wrap.querySelector('[data-multiselect-all]')?.addEventListener('click', () => {
        options().forEach((input) => {
          if (!input.closest('li')?.hidden) input.checked = true;
        });
        refresh();
      });
      wrap.querySelector('[data-multiselect-clear]')?.addEventListener('click', () => {
        options().forEach((input) => {
          input.checked = false;
        });
        refresh();
      });
      options().forEach((input) => input.addEventListener('change', refresh));
      document.addEventListener('click', (event) => {
        if (!wrap.contains(event.target) && panel && !panel.hasAttribute('hidden')) {
          panel.setAttribute('hidden', '');
          toggle?.setAttribute('aria-expanded', 'false');
        }
      });
      refresh();
    });
  }

  function bindActivityRows(root) {
    root.querySelectorAll('[data-activity-expand]').forEach((button) => {
      button.addEventListener('click', () => {
        const detailId = button.getAttribute('aria-controls');
        const detail = detailId ? document.getElementById(detailId) : null;
        if (!detail) return;
        const open = detail.hasAttribute('hidden');
        if (open) {
          detail.removeAttribute('hidden');
          button.setAttribute('aria-expanded', 'true');
          button.textContent = '▾';
        } else {
          detail.setAttribute('hidden', '');
          button.setAttribute('aria-expanded', 'false');
          button.textContent = '▸';
        }
      });
    });
  }

  function readJsonScript(id) {
    const script = document.getElementById(id);
    if (!script) return null;
    try {
      return JSON.parse(script.textContent);
    } catch (err) {
      return null;
    }
  }

  function applyScenarioPayload(form, payload, name) {
    if (!form || !payload) return;
    Object.keys(payload).forEach((key) => {
      const field = form.querySelector(`[name="${key}"]`);
      if (!field) return;
      if (field.type === 'checkbox') {
        field.checked = Boolean(payload[key]);
      } else {
        field.value = payload[key] == null ? '' : String(payload[key]);
      }
    });
    const nameField = form.querySelector('[name="scenario_name"]');
    if (nameField && name) nameField.value = name;
  }

  function syncAssignment(form) {
    const mode = form.querySelector('input[name="assignment_mode"]:checked');
    const roleBox = form.querySelector('[data-assignment-role]');
    const userBox = form.querySelector('[data-assignment-user]');
    if (!mode || !roleBox || !userBox) return;
    const isUser = mode.value === 'user';
    roleBox.hidden = isUser;
    userBox.hidden = !isUser;
    if (isUser) {
      const role = form.querySelector('#id_assignee_role, [name="assignee_role"]');
      if (role) role.value = '';
    } else {
      const user = form.querySelector('#id_specific_assignee, [name="specific_assignee"]');
      if (user) user.value = '';
    }
  }

  function collectRules(form) {
    const logic = form.querySelector('input[name="condition_logic"]:checked');
    const clauses = [];
    form.querySelectorAll('[data-rule-clause]').forEach((row) => {
      const field = row.querySelector('[data-rule-field]')?.value || '';
      const op = row.querySelector('[data-rule-op]')?.value || '=';
      const value = (row.querySelector('[data-rule-value]')?.value || '').trim();
      if (field && value) clauses.push({ field, op, value });
    });
    if (!clauses.length) return null;
    return { logic: logic ? logic.value : 'AND', clauses };
  }

  function writeRulesField(form) {
    const hidden = form.querySelector('[name="condition_rules_json"]');
    if (!hidden) return;
    const rules = collectRules(form);
    hidden.value = rules ? JSON.stringify(rules) : '';
  }

  function addClause(form, clause) {
    const holder = form.querySelector('[data-rule-clauses]');
    const tpl = form.querySelector('[data-rule-clause-template]');
    if (!holder || !tpl) return;
    const node = tpl.content.firstElementChild.cloneNode(true);
    if (clause) {
      const field = node.querySelector('[data-rule-field]');
      const op = node.querySelector('[data-rule-op]');
      const value = node.querySelector('[data-rule-value]');
      if (field) field.value = clause.field || 'value';
      if (op) op.value = clause.op || '=';
      if (value) value.value = clause.value || '';
    }
    holder.appendChild(node);
  }

  function loadInitialRules(form) {
    const script = document.getElementById('initial-condition-rules');
    let rules = null;
    if (script) {
      try {
        rules = JSON.parse(script.textContent);
      } catch (err) {
        rules = null;
      }
    }
    if (!rules || !rules.clauses || !rules.clauses.length) return;
    const logicInputs = form.querySelectorAll('input[name="condition_logic"]');
    logicInputs.forEach((input) => {
      input.checked = input.value === (rules.logic || 'AND');
    });
    rules.clauses.forEach((clause) => addClause(form, clause));
  }

  function showInspectorForm(root, opts) {
    const empty = root.querySelector('[data-inspector-empty]');
    const form = root.querySelector('[data-inspector-form]');
    const title = document.getElementById('workflow-inspector-title');
    if (!form) return;
    empty?.classList.add('is-hidden');
    form.classList.remove('is-hidden');
    const layout = root.querySelector('[data-designer-layout]');
    if (layout?.classList.contains('is-inspector-collapsed')) {
      setInspectorCollapsed(root, false);
    }
    if (opts && opts.insertAt != null) {
      delete root.dataset.selectedStep;
      const insertField = form.querySelector('[data-insert-at-field]');
      if (insertField) insertField.value = String(opts.insertAt);
      const addUrl = root.dataset.addUrl;
      if (addUrl) form.action = addUrl;
      const submit = form.querySelector('[data-inspector-submit]');
      if (submit) submit.textContent = 'Add step';
      const deleteBtn = form.querySelector('[data-delete-step]');
      if (deleteBtn) deleteBtn.hidden = true;
      if (title) title.textContent = 'Add step';
      form.querySelectorAll('input[type="text"], textarea').forEach((el) => {
        if (el.name === 'csrfmiddlewaretoken' || el.name === 'condition_rules_json' || el.name === 'insert_at') return;
        el.value = '';
      });
      form.querySelector('[data-rule-clauses]')?.replaceChildren();
      writeRulesField(form);
    }
    const first = form.querySelector('input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])');
    if (first) first.focus();
  }

  async function postForm(url, formData) {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'X-CSRFToken': csrfToken(),
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: formData,
      credentials: 'same-origin',
    });
    const data = await response.json().catch(() => ({ ok: false }));
    return { response, data };
  }

  function setInspectorCollapsed(root, collapsed) {
    const layout = root.querySelector('[data-designer-layout]');
    if (!layout) return;
    layout.classList.toggle('is-inspector-collapsed', collapsed);
    root.querySelectorAll('[data-toggle-inspector]').forEach((btn) => {
      btn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      if (btn.classList.contains('wf-designer-inspector-toggle')) {
        btn.hidden = !collapsed;
        btn.textContent = 'Show inspector';
      } else {
        btn.textContent = collapsed ? 'Expand' : 'Collapse';
      }
    });
  }

  function bindCanvasControls(root) {
    const stage = root.querySelector('[data-canvas-stage]');
    const viewport = root.querySelector('[data-canvas-viewport]');
    const label = root.querySelector('[data-zoom-label]');
    const zoomIn = root.querySelector('[data-zoom-in]');
    const zoomOut = root.querySelector('[data-zoom-out]');
    if (!stage || !viewport) return;

    let zoom = 1;

    const applyZoom = () => {
      zoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, zoom));
      stage.style.transform = `scale(${zoom})`;
      if (label) label.textContent = `${Math.round(zoom * 100)}%`;
      if (zoomOut) zoomOut.disabled = zoom <= ZOOM_MIN + 0.001;
      if (zoomIn) zoomIn.disabled = zoom >= ZOOM_MAX - 0.001;
    };

    const fit = () => {
      const viewRect = viewport.getBoundingClientRect();
      if (!viewRect.width) {
        zoom = 1;
        applyZoom();
        return;
      }
      const previous = zoom || 1;
      stage.style.transform = 'scale(1)';
      const natural = stage.getBoundingClientRect();
      const next = Math.min(
        ZOOM_MAX,
        Math.max(ZOOM_MIN, Math.min((viewRect.width - 64) / Math.max(natural.width, 1), (viewRect.height - 64) / Math.max(natural.height, 1))),
      );
      zoom = Number.isFinite(next) && next > 0 ? next : previous;
      applyZoom();
      // Keep Start/Completed in view after fit.
      const start = stage.querySelector('.wf-designer-boundary--start');
      const end = stage.querySelector('.wf-designer-boundary--end');
      if (start) start.scrollIntoView({ block: 'nearest', inline: 'nearest' });
      if (end) end.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    };

    zoomIn?.addEventListener('click', () => {
      zoom += ZOOM_STEP;
      applyZoom();
    });
    zoomOut?.addEventListener('click', () => {
      zoom -= ZOOM_STEP;
      applyZoom();
    });
    root.querySelector('[data-zoom-reset]')?.addEventListener('click', () => {
      zoom = 1;
      applyZoom();
      viewport.scrollLeft = 0;
      viewport.scrollTop = 0;
    });
    root.querySelector('[data-zoom-fit]')?.addEventListener('click', fit);

    viewport.addEventListener(
      'wheel',
      (event) => {
        if (!(event.ctrlKey || event.metaKey)) return;
        event.preventDefault();
        zoom += event.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP;
        applyZoom();
      },
      { passive: false },
    );

    let panning = false;
    let startX = 0;
    let startY = 0;
    let scrollLeft = 0;
    let scrollTop = 0;
    viewport.addEventListener('pointerdown', (event) => {
      if (event.button !== 0) return;
      if (event.target.closest('button, a, article, details, input, select, textarea, summary')) return;
      panning = true;
      viewport.classList.add('is-panning');
      startX = event.clientX;
      startY = event.clientY;
      scrollLeft = viewport.scrollLeft;
      scrollTop = viewport.scrollTop;
      viewport.setPointerCapture(event.pointerId);
    });
    viewport.addEventListener('pointermove', (event) => {
      if (!panning) return;
      viewport.scrollLeft = scrollLeft - (event.clientX - startX);
      viewport.scrollTop = scrollTop - (event.clientY - startY);
    });
    const endPan = () => {
      panning = false;
      viewport.classList.remove('is-panning');
    };
    viewport.addEventListener('pointerup', endPan);
    viewport.addEventListener('pointercancel', endPan);

    applyZoom();
    return {
      fit,
      setZoom: (value) => { zoom = value; applyZoom(); },
      getZoom: () => zoom,
      persist: () => {
        /* filled by caller */
      },
    };
  }

  function bindDesigner(root) {
    const form = root.querySelector('[data-inspector-form]');
    const canEdit = root.dataset.canEdit === 'true';
    const canvasApi = bindCanvasControls(root);
    restoreCanvas(root, canvasApi);
    const persist = () => persistCanvas(root, canvasApi);
    root.querySelector('[data-zoom-in]')?.addEventListener('click', persist);
    root.querySelector('[data-zoom-out]')?.addEventListener('click', persist);
    root.querySelector('[data-zoom-fit]')?.addEventListener('click', persist);
    root.querySelector('[data-zoom-reset]')?.addEventListener('click', persist);
    root.querySelector('[data-canvas-viewport]')?.addEventListener('scroll', persist, { passive: true });

    root.querySelectorAll('[data-toggle-inspector]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const layout = root.querySelector('[data-designer-layout]');
        const collapsed = !layout?.classList.contains('is-inspector-collapsed');
        setInspectorCollapsed(root, collapsed);
      });
    });

    const validationPanel = root.querySelector('[data-validation-panel]');
    root.querySelector('[data-open-validation]')?.addEventListener('click', () => {
      if (!validationPanel) return;
      validationPanel.hidden = false;
      validationPanel.classList.remove('is-collapsed');
      validationPanel.querySelector('[data-toggle-validation]')?.setAttribute('aria-expanded', 'true');
      validationPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
    root.querySelector('[data-toggle-validation]')?.addEventListener('click', () => {
      if (!validationPanel) return;
      const collapsed = validationPanel.classList.toggle('is-collapsed');
      root.querySelector('[data-toggle-validation]')?.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    });
    root.querySelectorAll('[data-validation-issue]').forEach((link) => {
      link.addEventListener('click', (event) => {
        const stepId = link.dataset.stepId;
        const field = link.dataset.focusField || '';
        if (!stepId) return;
        // Soft-navigate within page when already on the step.
        if (String(root.dataset.selectedStep) === String(stepId)) {
          event.preventDefault();
          centreStep(root, stepId);
          openInspectorSection(root, field);
          return;
        }
        try {
          sessionStorage.setItem(storageKey(root, 'focusField'), field);
        } catch (err) {
          /* ignore */
        }
      });
    });
    try {
      const pendingField = sessionStorage.getItem(storageKey(root, 'focusField'));
      if (pendingField && root.dataset.selectedStep) {
        sessionStorage.removeItem(storageKey(root, 'focusField'));
        centreStep(root, root.dataset.selectedStep);
        openInspectorSection(root, pendingField);
      } else if (root.dataset.selectedStep) {
        centreStep(root, root.dataset.selectedStep);
      }
    } catch (err) {
      /* ignore */
    }

    root.querySelectorAll('[data-toggle-remediation-issues]').forEach((button) => {
      button.addEventListener('click', () => {
        const panel = root.querySelector('[data-remediation-issues]');
        if (!panel) return;
        const open = panel.hasAttribute('hidden');
        if (open) panel.removeAttribute('hidden');
        else panel.setAttribute('hidden', '');
        button.setAttribute('aria-expanded', open ? 'true' : 'false');
        if (open) {
          const first = panel.querySelector('[data-validation-issue]');
          first?.focus();
        }
      });
    });
    root.querySelectorAll('[data-toggle-remediation-details]').forEach((button) => {
      button.addEventListener('click', () => {
        const panel = root.querySelector('[data-remediation-details]');
        if (!panel) return;
        const open = panel.hasAttribute('hidden');
        if (open) panel.removeAttribute('hidden');
        else panel.setAttribute('hidden', '');
        root.querySelectorAll('[data-toggle-remediation-details]').forEach((btn) => {
          btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
        if (open) panel.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      });
    });

    const publishDialog = root.querySelector('[data-publish-dialog]');
    const publishForm = root.querySelector('[data-publish-form]');
    root.querySelector('[data-publish-confirm]')?.addEventListener('click', () => {
      if (publishDialog && typeof publishDialog.showModal === 'function') {
        publishDialog.showModal();
      } else {
        publishForm?.requestSubmit();
      }
    });
    root.querySelector('[data-publish-submit]')?.addEventListener('click', () => {
      publishForm?.requestSubmit();
    });

    const openConfirm = (kind) => {
      const dialog = root.querySelector(`[data-confirm-dialog][data-confirm-kind="${kind}"]`);
      if (dialog && typeof dialog.showModal === 'function') dialog.showModal();
    };
    root.querySelector('[data-confirm-unpublish]')?.addEventListener('click', () => openConfirm('unpublish'));
    root.querySelector('[data-confirm-archive]')?.addEventListener('click', () => openConfirm('archive'));
    root.querySelector('[data-confirm-submit="unpublish"]')?.addEventListener('click', () => {
      root.querySelector('[data-unpublish-form]')?.requestSubmit();
    });
    root.querySelector('[data-confirm-submit="archive"]')?.addEventListener('click', () => {
      root.querySelector('[data-archive-form]')?.requestSubmit();
    });

    const testForm = root.querySelector('[data-test-form]');
    if (testForm) {
      syncScenarioSave(root);
      testForm.querySelector('[name="scenario_name"]')?.addEventListener('input', () => syncScenarioSave(root));

      const TEST_SCROLL_KEY = storageKey(root, 'test-scroll');
      const TEST_PRESET_KEY = storageKey(root, 'test-preset');
      const inputsPane = root.querySelector('.wf-test-pane--inputs');
      const resultsPane = root.querySelector('[data-test-results-pane]');

      const persistTestChrome = () => {
        try {
          sessionStorage.setItem(TEST_SCROLL_KEY, JSON.stringify({
            inputs: inputsPane?.scrollTop || 0,
            results: resultsPane?.scrollTop || 0,
            page: window.scrollY || 0,
          }));
          const activePreset = root.querySelector('[data-load-scenario].is-active');
          if (activePreset) {
            sessionStorage.setItem(TEST_PRESET_KEY, activePreset.dataset.scenarioKey || activePreset.dataset.scenarioName || '');
          }
        } catch (_err) { /* ignore quota */ }
      };

      const restoreTestChrome = () => {
        try {
          const scroll = JSON.parse(sessionStorage.getItem(TEST_SCROLL_KEY) || 'null');
          if (scroll) {
            if (inputsPane) inputsPane.scrollTop = scroll.inputs || 0;
            if (resultsPane) resultsPane.scrollTop = scroll.results || 0;
          }
          const preset = sessionStorage.getItem(TEST_PRESET_KEY) || '';
          if (preset) {
            root.querySelectorAll('[data-load-scenario]').forEach((btn) => {
              const match = (btn.dataset.scenarioKey || btn.dataset.scenarioName || '') === preset;
              btn.classList.toggle('is-active', match);
              btn.setAttribute('aria-pressed', match ? 'true' : 'false');
            });
          }
        } catch (_err) { /* ignore */ }
      };

      testForm.addEventListener('submit', persistTestChrome);
      inputsPane?.addEventListener('scroll', persistTestChrome, { passive: true });
      resultsPane?.addEventListener('scroll', persistTestChrome, { passive: true });
      window.requestAnimationFrame(restoreTestChrome);

      root.querySelector('[data-view-blocking-issues]')?.addEventListener('click', (event) => {
        const target = document.getElementById('wf-test-blocking-issues');
        if (!target) return;
        event.preventDefault();
        target.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        if (typeof target.focus === 'function') target.focus({ preventScroll: true });
      });
    }

    if (form) {
      form.addEventListener('change', (event) => {
        if (event.target && event.target.name === 'assignment_mode') syncAssignment(form);
        writeRulesField(form);
        if (canEdit) setDirty(root, true);
      });
      form.addEventListener('input', () => {
        writeRulesField(form);
        if (canEdit) setDirty(root, true);
      });
      form.querySelector('[data-add-clause]')?.addEventListener('click', () => {
        addClause(form);
        writeRulesField(form);
        setDirty(root, true);
      });
      form.querySelector('[data-rule-clauses]')?.addEventListener('click', (event) => {
        const btn = event.target.closest('[data-remove-clause]');
        if (!btn) return;
        btn.closest('[data-rule-clause]')?.remove();
        writeRulesField(form);
        setDirty(root, true);
      });
      loadInitialRules(form);
      syncAssignment(form);
      writeRulesField(form);

      let saveTimer = null;
      const scheduleAutosave = () => {
        if (!canEdit || !root.dataset.selectedStep) return;
        clearTimeout(saveTimer);
        saveTimer = setTimeout(async () => {
          writeRulesField(form);
          setStatus(root, 'Saving…', 'progress');
          const body = new FormData(form);
          const { response, data } = await postForm(form.action, body);
          if (response.ok && data.ok) {
            setStatus(root, 'All changes saved', 'success');
            setDirty(root, false);
          } else {
            setStatus(root, 'Save failed — retry', 'danger');
          }
        }, 800);
      };
      form.addEventListener('input', scheduleAutosave);
      form.addEventListener('change', scheduleAutosave);
    }

    const defaults = readJsonScript('default-test-scenarios') || [];
    const saved = readJsonScript('saved-test-scenarios') || [];
    root.querySelectorAll('[data-load-scenario]').forEach((button) => {
      button.addEventListener('click', () => {
        const key = button.dataset.scenarioKey;
        const name = button.dataset.scenarioName || button.textContent.trim();
        let payload = null;
        if (key) {
          const match = defaults.find((item) => item.key === key);
          payload = match ? match.payload : null;
        } else {
          const match = saved.find((item) => item.name === name);
          payload = match ? match.payload : null;
        }
        applyScenarioPayload(testForm, payload, name);
        root.querySelectorAll('[data-load-scenario]').forEach((btn) => {
          btn.classList.toggle('is-active', btn === button);
          btn.setAttribute('aria-pressed', btn === button ? 'true' : 'false');
        });
        syncScenarioSave(root);
      });
    });

    root.querySelector('[data-test-version-switch]')?.addEventListener('change', (event) => {
      const url = event.target.value;
      if (url) window.location.href = url;
    });

    bindMultiselect(root);
    bindActivityRows(root);

    root.querySelectorAll('[data-confirm-restore]').forEach((form) => {
      form.addEventListener('submit', (event) => {
        if (!window.confirm('Restore this version as a new draft? The historical version stays unchanged.')) {
          event.preventDefault();
        }
      });
    });

    root.querySelectorAll('[data-export-version-meta]').forEach((button) => {
      button.addEventListener('click', () => {
        const payload = {
          version: button.dataset.version,
          status: button.dataset.status,
          created_by: button.dataset.createdBy,
          published_by: button.dataset.publishedBy,
          exported_at: new Date().toISOString(),
        };
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `workflow-v${payload.version}-metadata.json`;
        link.click();
        URL.revokeObjectURL(url);
      });
    });

    const openAdd = (insertAt) => {
      if (!canEdit) return;
      showInspectorForm(root, { insertAt: insertAt || 1 });
    };

    root.querySelectorAll('[data-open-add-step]').forEach((button) => {
      button.addEventListener('click', () => openAdd(Number(button.dataset.insertAt || 1)));
    });
    root.querySelectorAll('.wf-designer-insert[data-insert-at]').forEach((button) => {
      button.addEventListener('click', () => openAdd(Number(button.dataset.insertAt || 1)));
    });

    const stepCards = () => Array.from(root.querySelectorAll('[data-step-id]'));

    const selectStep = (stepId) => {
      window.location.search = `?tab=design&step=${stepId}`;
    };

    stepCards().forEach((card) => {
      card.addEventListener('click', (event) => {
        if (event.target.closest('form, button, a, summary, details')) return;
        selectStep(card.dataset.stepId);
      });
      card.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          selectStep(card.dataset.stepId);
          return;
        }
        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
          event.preventDefault();
          const cards = stepCards();
          const index = cards.indexOf(card);
          const next = cards[index + 1] || cards[0];
          next?.focus();
        }
        if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
          event.preventDefault();
          const cards = stepCards();
          const index = cards.indexOf(card);
          const prev = cards[index - 1] || cards[cards.length - 1];
          prev?.focus();
        }
        if ((event.key === 'Delete' || event.key === 'Backspace') && canEdit) {
          const deleteBtn = form?.querySelector('[data-delete-step]');
          if (!deleteBtn || card.dataset.stepId !== root.dataset.selectedStep) return;
          event.preventDefault();
          if (window.confirm('Delete this workflow step?')) {
            deleteBtn.click();
          }
        }
      });
    });

    root.querySelector('[data-save-changes]')?.addEventListener('click', async () => {
      if (!form || !canEdit) return;
      writeRulesField(form);
      setStatus(root, 'Saving…', 'progress');
      if (!root.dataset.selectedStep || form.classList.contains('is-hidden')) {
        form.requestSubmit();
        return;
      }
      const body = new FormData(form);
      const { response, data } = await postForm(form.action, body);
      if (response.ok && data.ok) {
        setStatus(root, 'All changes saved', 'success');
        setDirty(root, false);
      } else {
        setStatus(root, 'Save failed — retry', 'danger');
        form.requestSubmit();
      }
    });

    document.addEventListener('keydown', (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
        if (!root.contains(document.activeElement) && document.activeElement !== document.body) return;
        const saveBtn = root.querySelector('[data-save-changes]');
        if (!saveBtn || saveBtn.disabled) return;
        event.preventDefault();
        saveBtn.click();
      }
      if (event.key === 'Escape') {
        if (publishDialog?.open) {
          publishDialog.close();
          return;
        }
        if (validationPanel && !validationPanel.hidden) {
          validationPanel.hidden = true;
          return;
        }
      }
      if ((event.metaKey || event.ctrlKey) && (event.key === '=' || event.key === '+')) {
        if (!root.querySelector('[data-canvas]')) return;
        event.preventDefault();
        root.querySelector('[data-zoom-in]')?.click();
      }
      if ((event.metaKey || event.ctrlKey) && event.key === '-') {
        if (!root.querySelector('[data-canvas]')) return;
        event.preventDefault();
        root.querySelector('[data-zoom-out]')?.click();
      }
      if ((event.metaKey || event.ctrlKey) && event.key === '0') {
        if (!root.querySelector('[data-canvas]')) return;
        event.preventDefault();
        root.querySelector('[data-zoom-reset]')?.click();
      }
    });

    if (!canEdit) return;
    let dragId = null;
    root.querySelectorAll('[data-step-id]').forEach((card) => {
      const handle = card.querySelector('[data-drag-handle]');
      if (!handle) return;

      handle.addEventListener('dragstart', (event) => {
        dragId = card.dataset.stepId;
        card.classList.add('is-dragging');
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', dragId);
      });
      handle.addEventListener('dragend', () => {
        card.classList.remove('is-dragging');
        dragId = null;
      });

      card.addEventListener('dragover', (event) => {
        event.preventDefault();
        card.classList.add('is-drop-target');
      });
      card.addEventListener('dragleave', () => card.classList.remove('is-drop-target'));
      card.addEventListener('drop', async (event) => {
        event.preventDefault();
        card.classList.remove('is-drop-target');
        const sourceId = event.dataTransfer.getData('text/plain') || dragId;
        const targetId = card.dataset.stepId;
        if (!sourceId || sourceId === targetId) return;
        const ids = Array.from(root.querySelectorAll('[data-step-id]')).map((el) => el.dataset.stepId);
        const from = ids.indexOf(sourceId);
        const to = ids.indexOf(targetId);
        if (from < 0 || to < 0) return;
        ids.splice(to, 0, ids.splice(from, 1)[0]);
        const body = new FormData();
        ids.forEach((id) => body.append('step_ids', id));
        setStatus(root, 'Saving…', 'progress');
        const { response, data } = await postForm(root.dataset.reorderUrl, body);
        if (response.ok && data.ok) {
          setStatus(root, 'All changes saved', 'success');
          window.location.reload();
        } else {
          setStatus(root, 'Reorder failed', 'danger');
        }
      });
    });

    void canvasApi;
  }

  ready(() => {
    const root = document.querySelector('[data-workflow-designer]');
    if (root) bindDesigner(root);
  });
})();
