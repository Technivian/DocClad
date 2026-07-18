from django.contrib.auth import get_user_model
from django.test import TestCase

from contracts.models import AuditLog, Organization
from contracts.services.audit import append_audit, verify_chain


class AuditAccountRetentionTests(TestCase):
    def test_deleting_an_account_keeps_the_hashed_audit_actor_id(self):
        user = get_user_model().objects.create_user(username='former-user', password='test-password')
        organization = Organization.objects.create(name='Retention Org', slug='retention-org')
        entry = append_audit(
            user=user,
            action=AuditLog.Action.VIEW,
            event_type='retention.account_cleanup_test',
            model_name='Contract',
            organization=organization,
        )
        actor_id = user.pk

        user.delete()

        entry.refresh_from_db()
        self.assertEqual(entry.user_id, actor_id)
        self.assertEqual(verify_chain(organization.pk)['status'], 'valid')
