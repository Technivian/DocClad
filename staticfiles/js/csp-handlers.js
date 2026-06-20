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

  function applyTheme(next) {
    document.documentElement.setAttribute('data-theme', next);
    try {
      localStorage.setItem('cms-aegis-theme', next);
    } catch (e) {
      /* storage unavailable; theme still applies for this page */
    }
  }

  // Kept on window so any remaining/legacy caller resolves during transition.
  window.toggleTheme = function () {
    var current = document.documentElement.getAttribute('data-theme');
    applyTheme(current === 'dark' ? 'light' : 'dark');
  };

  // data-action="toggle-theme" | "demo-alert" (data-message)
  document.addEventListener('click', function (e) {
    var el = e.target.closest('[data-action]');
    if (!el) {
      return;
    }
    var action = el.getAttribute('data-action');
    if (action === 'toggle-theme') {
      e.preventDefault();
      window.toggleTheme();
    } else if (action === 'demo-alert') {
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
})();
