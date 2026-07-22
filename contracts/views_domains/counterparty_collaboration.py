"""Contract-scoped counterparty collaboration.

The external portal is deliberately isolated from the authenticated product:
participants receive a revocable, expiring capability link and must confirm the
invited email before a session grants access.  It never creates a workspace
membership or exposes internal notes, approvals, AI review, or search.
"""
from datetime import timedelta
from hmac import compare_digest

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db.models import Q

from contracts.forms import CounterpartyCollaborationInviteForm
from contracts.middleware import log_action
from contracts.models import (
    AuditLog,
    Contract,
    CounterpartyCollaborationItem,
    CounterpartyCollaborationParticipant,
    Document,
)
from contracts.permissions import ContractAction, can_access_contract_action
from contracts.tenancy import get_user_organization


PORTAL_SESSION_PREFIX = 'counterparty-collaboration:'


def _portal_session_key(participant):
    return f'{PORTAL_SESSION_PREFIX}{participant.token}'


def _portal_participant_or_404(token):
    participant = get_object_or_404(
        CounterpartyCollaborationParticipant.objects.select_related('contract', 'organization'),
        token=token,
    )
    if not participant.is_accessible:
        # Do not distinguish revoked, expired, or invalid links to an external
        # visitor. This prevents the link from becoming an account oracle.
        raise Http404
    return participant


def _verified_portal_participant_or_404(request, token):
    participant = _portal_participant_or_404(token)
    verified_email = request.session.get(_portal_session_key(participant))
    if not verified_email or not compare_digest(verified_email.lower(), participant.email.lower()):
        raise Http404
    return participant


def _audit_external(request, participant, *, action, event_type, changes=None, outcome=AuditLog.Outcome.SUCCESS):
    data = {'event': event_type, 'contract_id': participant.contract_id, 'participant_id': participant.pk}
    if changes:
        data.update(changes)
    return log_action(
        None, action, 'CounterpartyCollaborationParticipant', participant.pk,
        participant.email, organization=participant.organization,
        event_type=event_type, actor_type=AuditLog.ActorType.HUMAN,
        outcome=outcome, changes=data, request=request,
    )


@login_required
@require_POST
def counterparty_collaboration_invite(request, pk):
    organization = get_user_organization(request.user)
    contract = get_object_or_404(Contract.objects.filter(organization=organization), pk=pk)
    if not can_access_contract_action(request.user, contract, ContractAction.EDIT):
        return HttpResponseForbidden('You do not have permission to invite counterparty collaborators.')

    form = CounterpartyCollaborationInviteForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Enter a valid email address to create the invitation.')
        return redirect('contracts:contract_detail', pk=contract.pk)

    email = form.cleaned_data['email']
    active = CounterpartyCollaborationParticipant.objects.filter(
        contract=contract,
        email__iexact=email,
        status__in=[
            CounterpartyCollaborationParticipant.Status.PENDING,
            CounterpartyCollaborationParticipant.Status.ACTIVE,
        ],
    ).filter(expires_at__gt=timezone.now()).first()
    if active:
        messages.info(request, f'An active counterparty invitation already exists for {email}.')
        return redirect('contracts:contract_detail', pk=contract.pk)

    participant = form.save(commit=False)
    participant.organization = organization
    participant.contract = contract
    participant.invited_by = request.user
    participant.expires_at = timezone.now() + timedelta(days=14)
    participant.save()
    portal_url = request.build_absolute_uri(
        reverse('contracts:counterparty_collaboration_portal', kwargs={'token': participant.token})
    )
    log_action(
        request.user, AuditLog.Action.CREATE, 'CounterpartyCollaborationParticipant', participant.pk,
        participant.email, organization=organization, event_type='counterparty_collaboration.invited',
        changes={
            'event': 'counterparty_collaboration.invited', 'contract_id': contract.pk,
            'permissions': {
                'view_documents': participant.can_view_documents,
                'comment': participant.can_comment,
                'upload_revisions': participant.can_upload_revisions,
            },
        }, request=request,
    )
    try:
        send_mail(
            subject=f'Collaboration invitation: {contract.title}',
            message=(
                f'You have been invited to collaborate on "{contract.title}" in CLM One.\n\n'
                f'Open the secure collaboration workspace: {portal_url}\n\n'
                'This link is restricted to the invited email address and expires in 14 days.'
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            recipient_list=[participant.email],
            fail_silently=False,
        )
        messages.success(request, f'Counterparty invitation sent to {participant.email}.')
    except Exception:
        # The invitation remains usable; never include a mail-provider error.
        messages.warning(request, f'Invitation created for {participant.email}. Share this secure link: {portal_url}')
    return redirect('contracts:contract_detail', pk=contract.pk)


@login_required
@require_POST
def counterparty_collaboration_revoke(request, pk, participant_id):
    organization = get_user_organization(request.user)
    contract = get_object_or_404(Contract.objects.filter(organization=organization), pk=pk)
    if not can_access_contract_action(request.user, contract, ContractAction.EDIT):
        return HttpResponseForbidden('You do not have permission to revoke counterparty access.')
    participant = get_object_or_404(
        CounterpartyCollaborationParticipant.objects.filter(contract=contract, organization=organization),
        pk=participant_id,
    )
    participant.status = CounterpartyCollaborationParticipant.Status.REVOKED
    participant.save(update_fields=['status', 'updated_at'])
    request.session.pop(_portal_session_key(participant), None)
    log_action(
        request.user, AuditLog.Action.UPDATE, 'CounterpartyCollaborationParticipant', participant.pk,
        participant.email, organization=organization, event_type='counterparty_collaboration.revoked',
        changes={'event': 'counterparty_collaboration.revoked', 'contract_id': contract.pk}, request=request,
    )
    messages.success(request, f'Access revoked for {participant.email}.')
    return redirect('contracts:contract_detail', pk=contract.pk)


@login_required
@require_POST
def counterparty_collaboration_create_item(request, pk):
    organization = get_user_organization(request.user)
    contract = get_object_or_404(Contract.objects.filter(organization=organization), pk=pk)
    if not can_access_contract_action(request.user, contract, ContractAction.EDIT):
        return HttpResponseForbidden('You do not have permission to create counterparty tasks.')
    kind = request.POST.get('kind')
    if kind not in (CounterpartyCollaborationItem.Kind.COMMENT, CounterpartyCollaborationItem.Kind.TASK):
        messages.error(request, 'Choose a valid collaboration item type.')
        return redirect('contracts:contract_detail', pk=contract.pk)
    title = (request.POST.get('title') or '').strip()
    content = (request.POST.get('content') or '').strip()
    if kind == CounterpartyCollaborationItem.Kind.TASK and not title:
        messages.error(request, 'A task needs a title.')
        return redirect('contracts:contract_detail', pk=contract.pk)
    if not title and not content:
        messages.error(request, 'Enter a message or task.')
        return redirect('contracts:contract_detail', pk=contract.pk)
    item = CounterpartyCollaborationItem.objects.create(
        organization=organization, contract=contract, created_by=request.user,
        kind=kind, title=title, content=content,
    )
    log_action(
        request.user, AuditLog.Action.CREATE, 'CounterpartyCollaborationItem', item.pk,
        str(item), organization=organization, event_type='counterparty_collaboration.item_created',
        changes={'event': 'counterparty_collaboration.item_created', 'contract_id': contract.pk, 'kind': item.kind},
        request=request,
    )
    messages.success(request, 'Counterparty collaboration item created.')
    return redirect('contracts:contract_detail', pk=contract.pk)


def counterparty_collaboration_portal(request, token):
    participant = _portal_participant_or_404(token)
    session_key = _portal_session_key(participant)
    verified_email = request.session.get(session_key)

    if request.method == 'POST':
        supplied_email = (request.POST.get('email') or '').strip().lower()
        if not supplied_email or not compare_digest(supplied_email, participant.email.lower()):
            _audit_external(
                request, participant, action=AuditLog.Action.VIEW,
                event_type='counterparty_collaboration.access_blocked',
                changes={'reason': 'email_confirmation_failed'}, outcome=AuditLog.Outcome.BLOCKED,
            )
            return render(request, 'contracts/counterparty_collaboration_access.html', {
                'participant': participant, 'invalid_email': True,
            }, status=403)
        request.session[session_key] = participant.email.lower()
        request.session.set_expiry(60 * 60 * 8)
        now = timezone.now()
        changed = []
        if participant.status == CounterpartyCollaborationParticipant.Status.PENDING:
            participant.status = CounterpartyCollaborationParticipant.Status.ACTIVE
            participant.accepted_at = now
            changed.extend(['status', 'accepted_at'])
        participant.last_seen_at = now
        changed.extend(['last_seen_at', 'updated_at'])
        participant.save(update_fields=changed)
        _audit_external(request, participant, action=AuditLog.Action.VIEW,
                        event_type='counterparty_collaboration.access_granted')
        return redirect('contracts:counterparty_collaboration_portal', token=participant.token)

    if not verified_email or not compare_digest(verified_email.lower(), participant.email.lower()):
        return render(request, 'contracts/counterparty_collaboration_access.html', {'participant': participant})

    participant.last_seen_at = timezone.now()
    participant.save(update_fields=['last_seen_at', 'updated_at'])
    shared_documents = []
    if participant.can_view_documents:
        shared_documents = participant.contract.documents.filter(
            share_with_counterparty=True, is_privileged=False, is_deleted=False,
        ).only('id', 'title', 'version', 'document_type', 'updated_at', 'file').order_by('-updated_at')
    items = participant.contract.counterparty_collaboration_items.filter(
        Q(document__isnull=True) | Q(
            document__share_with_counterparty=True,
            document__is_privileged=False,
            document__is_deleted=False,
        )
    ).select_related('participant', 'document', 'created_by')[:50]
    return render(request, 'contracts/counterparty_collaboration_portal.html', {
        'participant': participant,
        'contract': participant.contract,
        'shared_documents': shared_documents,
        'items': items,
    })


@require_POST
def counterparty_collaboration_add_comment(request, token):
    participant = _verified_portal_participant_or_404(request, token)
    if not participant.can_comment:
        raise Http404
    content = (request.POST.get('content') or '').strip()
    if not content:
        return redirect('contracts:counterparty_collaboration_portal', token=participant.token)
    item = CounterpartyCollaborationItem.objects.create(
        organization=participant.organization, contract=participant.contract, participant=participant,
        kind=CounterpartyCollaborationItem.Kind.COMMENT, content=content,
    )
    _audit_external(request, participant, action=AuditLog.Action.CREATE,
                    event_type='counterparty_collaboration.comment_added',
                    changes={'item_id': item.pk})
    return redirect('contracts:counterparty_collaboration_portal', token=participant.token)


@require_POST
def counterparty_collaboration_upload_revision(request, token):
    participant = _verified_portal_participant_or_404(request, token)
    if not participant.can_upload_revisions:
        raise Http404
    upload = request.FILES.get('file')
    if not upload:
        return redirect('contracts:counterparty_collaboration_portal', token=participant.token)
    # Reuse the product's conservative upload ceiling; no type is trusted from
    # the browser and internal review still governs downstream use.
    if upload.size > 50 * 1024 * 1024:
        return render(request, 'contracts/counterparty_collaboration_portal.html', {
            'participant': participant, 'contract': participant.contract,
            'shared_documents': [], 'items': participant.contract.counterparty_collaboration_items.all()[:50],
            'upload_error': 'The revision must be 50 MB or smaller.',
        }, status=400)
    title = (request.POST.get('title') or '').strip() or upload.name.rsplit('.', 1)[0]
    from contracts.services.document_version_service import create_document_version

    document, _version = create_document_version(
        organization=participant.organization,
        title=title,
        document_type=Document.DocType.CONTRACT,
        status=Document.Status.DRAFT,
        contract=participant.contract,
        file=upload,
        uploaded_by=None,
        actor=None,
        source='counterparty_revision',
        is_confidential=True,
        share_with_counterparty=True,
        request=request,
        supersede_prior=False,
    )
    item = CounterpartyCollaborationItem.objects.create(
        organization=participant.organization, contract=participant.contract, participant=participant,
        document=document, kind=CounterpartyCollaborationItem.Kind.REVISION,
        title=f'Revision shared: {document.title}', content=(request.POST.get('comment') or '').strip(),
    )
    _audit_external(request, participant, action=AuditLog.Action.CREATE,
                    event_type='counterparty_collaboration.revision_uploaded',
                    changes={'item_id': item.pk, 'document_id': document.pk})
    return redirect('contracts:counterparty_collaboration_portal', token=participant.token)


@require_POST
def counterparty_collaboration_complete_task(request, token, item_id):
    participant = _verified_portal_participant_or_404(request, token)
    if not participant.can_comment:
        raise Http404
    item = get_object_or_404(
        CounterpartyCollaborationItem.objects.filter(contract=participant.contract, kind=CounterpartyCollaborationItem.Kind.TASK),
        pk=item_id,
    )
    item.status = CounterpartyCollaborationItem.Status.COMPLETED
    item.completed_at = timezone.now()
    item.save(update_fields=['status', 'completed_at', 'updated_at'])
    _audit_external(request, participant, action=AuditLog.Action.UPDATE,
                    event_type='counterparty_collaboration.task_completed', changes={'item_id': item.pk})
    return redirect('contracts:counterparty_collaboration_portal', token=participant.token)


def counterparty_collaboration_document_download(request, token, document_id):
    participant = _verified_portal_participant_or_404(request, token)
    if not participant.can_view_documents:
        raise Http404
    document = get_object_or_404(
        Document.objects.filter(
            contract=participant.contract, share_with_counterparty=True,
            is_privileged=False, is_deleted=False,
        ),
        pk=document_id,
    )
    if not document.file:
        raise Http404
    _audit_external(request, participant, action=AuditLog.Action.VIEW,
                    event_type='counterparty_collaboration.document_downloaded',
                    changes={'document_id': document.pk})
    try:
        return FileResponse(document.file.open('rb'), as_attachment=True, filename=document.file.name.rsplit('/', 1)[-1])
    except Exception:
        raise Http404
