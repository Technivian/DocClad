/**
 * Organization Team: invite dialog, role dialog, copy invite link.
 */
(function () {
  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  function bindConfirmForms(root) {
    root.querySelectorAll('form[data-confirm]').forEach((form) => {
      form.addEventListener('submit', (event) => {
        const message = form.getAttribute('data-confirm');
        if (message && !window.confirm(message)) {
          event.preventDefault();
        }
      });
    });
  }

  function bindInviteDialog(root) {
    const dialog = document.getElementById('org-team-invite-dialog');
    if (!dialog) return;
    const openers = document.querySelectorAll('[data-open-invite-dialog]');
    const closers = dialog.querySelectorAll('[data-close-invite-dialog]');
    const form = dialog.querySelector('.org-team-invite-form');
    openers.forEach((btn) => {
      btn.addEventListener('click', (event) => {
        event.preventDefault();
        dialog.showModal();
        const email = dialog.querySelector('#id_email');
        if (email) email.focus();
      });
    });
    closers.forEach((btn) => btn.addEventListener('click', () => dialog.close()));
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) dialog.close();
    });
    form?.addEventListener('submit', () => {
      const submit = form.querySelector('button[type="submit"]');
      if (submit) {
        submit.disabled = true;
        submit.setAttribute('aria-busy', 'true');
        submit.textContent = 'Sending…';
      }
    });
    if (root.hasAttribute('data-open-invite')) {
      dialog.showModal();
    }
  }

  function bindRoleDialog(root) {
    const dialog = document.getElementById('org-team-role-dialog');
    if (!dialog) return;
    const form = dialog.querySelector('[data-role-dialog-form]');
    const select = dialog.querySelector('[data-role-dialog-select]');
    const hidden = dialog.querySelector('[data-role-dialog-value]');
    const copy = dialog.querySelector('[data-role-dialog-copy]');
    const warning = dialog.querySelector('[data-role-dialog-warning]');
    const closers = dialog.querySelectorAll('[data-close-role-dialog]');

    function syncWarning() {
      if (!select || !warning) return;
      const elevated = select.value === 'OWNER' || select.value === 'ADMIN';
      warning.classList.toggle('is-hidden', !elevated);
    }

    select?.addEventListener('change', () => {
      if (hidden) hidden.value = select.value;
      syncWarning();
    });

    closers.forEach((btn) => btn.addEventListener('click', () => dialog.close()));
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) dialog.close();
    });

    form?.addEventListener('submit', (event) => {
      if (!select) return;
      if (hidden) hidden.value = select.value;
      if (select.value === 'OWNER' || select.value === 'ADMIN') {
        const ok = window.confirm(
          select.value === 'OWNER'
            ? 'Grant Owner access? This person will have full control of the organization.'
            : 'Grant Admin access? This person will be able to manage members and invitations.'
        );
        if (!ok) event.preventDefault();
      }
    });

    root.querySelectorAll('[data-open-role-dialog]').forEach((button) => {
      button.addEventListener('click', () => {
        const url = button.getAttribute('data-action-url');
        const name = button.getAttribute('data-member-name') || 'this member';
        const current = button.getAttribute('data-current-role') || '';
        let roles = [];
        try {
          roles = JSON.parse(button.getAttribute('data-assignable-roles') || '[]');
        } catch (err) {
          roles = [];
        }
        if (!form || !select || !url) return;
        form.action = url;
        if (copy) copy.textContent = `Update access for ${name}.`;
        select.innerHTML = '';
        roles.forEach((role) => {
          const option = document.createElement('option');
          option.value = role.value;
          option.textContent = role.label;
          if (role.value === current) option.selected = true;
          select.appendChild(option);
        });
        if (hidden) hidden.value = select.value;
        syncWarning();
        dialog.showModal();
        // Close parent kebab
        const kebab = button.closest('details.wq-kebab');
        if (kebab) kebab.open = false;
      });
    });
  }

  function bindCopyLinks(root) {
    root.querySelectorAll('[data-copy-invite-link]').forEach((button) => {
      button.addEventListener('click', async () => {
        const url = button.getAttribute('data-invite-url') || '';
        if (!url) return;
        try {
          await navigator.clipboard.writeText(url);
          const original = button.textContent;
          button.textContent = 'Link copied';
          setTimeout(() => {
            button.textContent = original;
          }, 1600);
        } catch (err) {
          window.prompt('Copy invitation link:', url);
        }
        const kebab = button.closest('details.wq-kebab');
        if (kebab) kebab.open = false;
      });
    });
  }

  ready(() => {
    const root = document.querySelector('[data-organization-team]');
    if (!root) return;
    bindConfirmForms(root);
    bindInviteDialog(root);
    bindRoleDialog(root);
    bindCopyLinks(root);
  });
})();
