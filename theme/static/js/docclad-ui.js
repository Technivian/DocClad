/* Casefile interaction runtime: shared command palette and toast feedback. */
(function () {
  'use strict';

  var DocClad = window.DocClad = window.DocClad || {};

  DocClad.chartTheme = Object.freeze({
    colors: ['#1B7F5A', '#4568A6', '#9A6517', '#765B8C', '#A7463F'],
    grid: '#DFE3E7',
    axis: '#69717C',
    text: '#171A1F',
    surface: '#FFFFFF',
    fontFamily: 'Inter, system-ui, sans-serif'
  });

  DocClad.motion = Object.freeze({
    animate: function (element, keyframes, options) {
      if (!element || typeof element.animate !== 'function') return null;
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return null;
      return element.animate(keyframes, Object.assign({
        duration: 180,
        easing: 'cubic-bezier(.2, 0, 0, 1)',
        fill: 'both'
      }, options || {}));
    }
  });

  DocClad.dataTable = Object.freeze({
    setBusy: function (table, busy) {
      if (!table) return;
      table.setAttribute('aria-busy', busy ? 'true' : 'false');
    },
    setSort: function (table, columnKey, direction) {
      if (!table) return;
      table.querySelectorAll('[data-column-key]').forEach(function (header) {
        var active = header.getAttribute('data-column-key') === columnKey;
        header.setAttribute('aria-sort', active ? direction : 'none');
      });
    }
  });

  DocClad.toast = function (message, options) {
    options = options || {};
    var region = document.getElementById('docclad-toast-region');
    if (!region || !message) return null;

    var tone = ['success', 'attention', 'danger', 'info'].indexOf(options.tone) >= 0 ? options.tone : 'info';
    var toast = document.createElement('div');
    toast.className = 'dc-toast dc-toast--' + tone;
    toast.setAttribute('role', tone === 'danger' ? 'alert' : 'status');

    var marker = document.createElement('span');
    marker.className = 'dc-toast__marker';
    marker.setAttribute('aria-hidden', 'true');
    marker.textContent = tone === 'success' ? '\u2713' : tone === 'danger' ? '!' : tone === 'attention' ? '!' : 'i';

    var copy = document.createElement('span');
    copy.className = 'dc-toast__copy';
    copy.textContent = String(message);
    toast.appendChild(marker);
    toast.appendChild(copy);
    region.appendChild(toast);

    var duration = Number(options.duration || 4200);
    var timer = window.setTimeout(remove, duration);
    function remove() {
      window.clearTimeout(timer);
      toast.classList.add('is-leaving');
      window.setTimeout(function () { toast.remove(); }, 160);
    }
    toast.addEventListener('mouseenter', function () { window.clearTimeout(timer); });
    toast.addEventListener('mouseleave', function () { timer = window.setTimeout(remove, 1200); });
    return { dismiss: remove, element: toast };
  };

  document.addEventListener('click', function (event) {
    var trigger = event.target.closest('[data-toast-message]');
    if (!trigger) return;
    DocClad.toast(trigger.getAttribute('data-toast-message'), {
      tone: trigger.getAttribute('data-toast-tone') || 'info'
    });
  });

  function initCommandPalette() {
    var dialog = document.getElementById('docclad-command-palette');
    if (!dialog || typeof dialog.showModal !== 'function') return;

    var input = dialog.querySelector('[data-command-input]');
    var items = Array.prototype.slice.call(dialog.querySelectorAll('[data-command-item]'));
    var empty = dialog.querySelector('[data-command-empty]');
    var previousFocus = null;

    function filter() {
      var term = (input.value || '').trim().toLowerCase();
      var visible = 0;
      items.forEach(function (item) {
        var match = !term || (item.getAttribute('data-command-search') || '').indexOf(term) >= 0;
        item.hidden = !match;
        if (match) visible += 1;
      });
      if (empty) empty.hidden = visible !== 0;
      dialog.querySelectorAll('[data-command-group]').forEach(function (group) {
        group.hidden = !group.querySelector('[data-command-item]:not([hidden])');
      });
    }

    function open() {
      if (dialog.open) return;
      previousFocus = document.activeElement;
      dialog.showModal();
      input.value = '';
      filter();
      window.requestAnimationFrame(function () { input.focus(); });
    }

    function close() {
      if (!dialog.open) return;
      dialog.close();
      if (previousFocus && typeof previousFocus.focus === 'function') previousFocus.focus();
    }

    document.addEventListener('keydown', function (event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        dialog.open ? close() : open();
      }
    });
    document.addEventListener('click', function (event) {
      if (event.target.closest('[data-command-trigger]')) {
        event.preventDefault();
        open();
      }
      if (event.target.closest('[data-command-close]')) close();
    });
    dialog.addEventListener('click', function (event) { if (event.target === dialog) close(); });
    dialog.addEventListener('cancel', function (event) { event.preventDefault(); close(); });
    input.addEventListener('input', filter);
    DocClad.commandPalette = { open: open, close: close };
  }

  function initServerToasts() {
    document.querySelectorAll('[data-server-toast]').forEach(function (message) {
      DocClad.toast(message.getAttribute('data-toast-message'), {
        tone: message.getAttribute('data-toast-tone') || 'info'
      });
      message.remove();
    });
  }

  function initDataTables() {
    document.querySelectorAll('[data-table-core]').forEach(function (table) {
      table.setAttribute('data-casefile-ready', 'true');
      if (!table.hasAttribute('aria-busy')) table.setAttribute('aria-busy', 'false');
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initCommandPalette();
      initServerToasts();
      initDataTables();
    });
  } else {
    initCommandPalette();
    initServerToasts();
    initDataTables();
  }
})();
