/*
 * Delegated event handlers for behaviors that used to be inline `onclick` /
 * `onchange` / `onsubmit` attributes. Inline handlers are blocked once
 * 'unsafe-inline' is removed from the CSP script-src (and nonces do not cover
 * inline handlers), so these are wired here via event delegation on `document`.
 *
 * Loaded as an external <script src> (no nonce required) from both base shells.
 * Delegation also covers dynamically-injected elements (e.g. clause cards).
 */
(function () {
  'use strict';

  // data-action="demo-alert" (data-message)
  document.addEventListener('click', function (e) {
    var el = e.target.closest('[data-action]');
    if (!el) {
      return;
    }
    var action = el.getAttribute('data-action');
    if (action === 'demo-alert') {
      window.alert(el.getAttribute('data-message') || '');
    }
  });

  // data-autosubmit: submit the owning form when the control changes
  // (replaces onchange="this.form.submit()"). Uses .submit() to preserve the
  // original behavior of bypassing validation / the submit event.
  document.addEventListener('change', function (e) {
    var el = e.target.closest('[data-autosubmit]');
    if (el && el.form) {
      el.form.submit();
    }
  });

  // data-confirm="message": block submit unless confirmed
  // (replaces onsubmit="return confirm('...')").
  document.addEventListener('submit', function (e) {
    var form = e.target.closest('form[data-confirm]');
    if (form && !window.confirm(form.getAttribute('data-confirm'))) {
      e.preventDefault();
    }
  });

  // DPA option pickers use native <details> elements so their checkboxes work
  // without JavaScript. Match expected menu behaviour by closing an open list
  // when the user continues elsewhere on the page, or presses Escape.
  document.addEventListener('click', function (e) {
    document.querySelectorAll('.dpa-option-picker[open]').forEach(function (picker) {
      if (!picker.contains(e.target)) {
        picker.removeAttribute('open');
      }
    });
  });

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') {
      return;
    }
    document.querySelectorAll('.dpa-option-picker[open]').forEach(function (picker) {
      picker.removeAttribute('open');
    });
  });
})();
