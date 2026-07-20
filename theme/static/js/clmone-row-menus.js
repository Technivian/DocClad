/**
 * Fixed-position row kebab menus for dense tables.
 * Prevents absolute menus from stretching table rows or being clipped.
 */
(function () {
  'use strict';

  function placeMenu(menu) {
    var panel = menu.querySelector('.wq-kebab-menu');
    var trigger = menu.querySelector('.wq-kebab-trigger, summary');
    if (!panel || !trigger || !menu.open) return;

    var rect = trigger.getBoundingClientRect();
    var menuWidth = Math.max(panel.offsetWidth || 180, 180);
    var left = Math.min(rect.right - menuWidth, window.innerWidth - menuWidth - 8);
    left = Math.max(8, left);
    var top = rect.bottom + 4;
    panel.style.top = top + 'px';
    panel.style.left = left + 'px';

    var panelHeight = panel.offsetHeight || 0;
    if (top + panelHeight > window.innerHeight - 8) {
      panel.style.top = Math.max(8, rect.top - panelHeight - 4) + 'px';
    }
  }

  function clearPlacement(menu) {
    var panel = menu.querySelector('.wq-kebab-menu');
    if (!panel) return;
    panel.style.top = '';
    panel.style.left = '';
  }

  function setRowActive(menu, active) {
    var row = menu.closest('tr');
    if (!row) return;
    row.classList.toggle('is-row-active', !!active);
  }

  function closeMenu(menu) {
    if (!menu.open) return;
    menu.removeAttribute('open');
    clearPlacement(menu);
    setRowActive(menu, false);
  }

  function closeAll(except) {
    document.querySelectorAll('details.wq-kebab[open]').forEach(function (menu) {
      if (except && menu === except) return;
      closeMenu(menu);
    });
  }

  function bindMenu(menu) {
    if (menu.dataset.clmoneRowMenuBound === '1') return;
    menu.dataset.clmoneRowMenuBound = '1';

    menu.addEventListener('toggle', function () {
      if (menu.open) {
        closeAll(menu);
        setRowActive(menu, true);
        requestAnimationFrame(function () {
          placeMenu(menu);
        });
        return;
      }
      clearPlacement(menu);
      setRowActive(menu, false);
    });

    menu.addEventListener('click', function (event) {
      event.stopPropagation();
    });
  }

  function init(root) {
    var scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('details.wq-kebab').forEach(bindMenu);
  }

  document.addEventListener('click', function (event) {
    if (event.target.closest('details.wq-kebab')) return;
    closeAll();
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') closeAll();
  });

  window.addEventListener('scroll', function () {
    closeAll();
  }, true);

  window.addEventListener('resize', function () {
    closeAll();
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      init(document);
    });
  } else {
    init(document);
  }

  window.CLMOneRowMenus = {
    init: init,
    placeMenu: placeMenu,
    closeAll: closeAll,
  };
})();
