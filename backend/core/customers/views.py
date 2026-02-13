from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from customers.models import CompanyMembership, ProducerProfile, TenantEmailConfig
from customers.serializers import (
    CompanyMembershipReadSerializer,
    CompanyMembershipUpdateSerializer,
    CompanyMembershipUpsertSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProducerProfilePatchSerializer,
    ProducerProfileReadSerializer,
    ProducerProfileUpsertSerializer,
    TenantEmailConfigSerializer,
    TenantEmailConfigTestSerializer,
)
from customers.services import EmailService, TenantEmailServiceError
from finance.models import Payable
from operational.models import SalesGoal
from tenancy.permissions import (
    IsAuthenticatedTenantMember,
    IsTenantOwner,
    IsTenantRoleAllowed,
)
from tenancy.rbac import (
    get_resource_role_matrices,
    normalize_rbac_overrides,
    resource_capabilities_for_role,
    serialize_role_matrices,
    validate_rbac_overrides_schema,
)


def _build_portal_reset_url(request, uid: str, token: str) -> str:
    # Prefer upstream proxies (Cloud Run / LB) when present.
    forwarded_proto = (request.headers.get("X-Forwarded-Proto") or "").strip()
    scheme = forwarded_proto or ("https" if not settings.DEBUG else request.scheme)
    host = (request.get_host() or "").split(":", 1)[0].strip()
    return f"{scheme}://{host}/reset-password?uid={uid}&token={token}"


class PasswordResetRequestAPIView(APIView):
    """Request a password reset token.

    Security:
    - Always returns 200 to avoid leaking whether a user exists.
    - Sends reset instructions to the user's email when available.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data.get("email")
        username = serializer.validated_data.get("username")

        User = get_user_model()
        queryset = User.objects.all()
        if username:
            queryset = queryset.filter(username__iexact=username)
        if email:
            queryset = queryset.filter(email__iexact=email)

        user = queryset.only("id", "email").first()
        reset_url = None
        if user and getattr(user, "email", ""):
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = _build_portal_reset_url(request, uid, token)

            subject = "Redefinição de senha"
            message = (
                "Você solicitou a redefinição de senha.\n\n"
                f"Acesse o link para definir uma nova senha:\n{reset_url}\n\n"
                "Se você não solicitou isso, ignore este email."
            )
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=[user.email],
                fail_silently=True,
            )

        payload = {"detail": "If the account exists, you will receive reset instructions shortly."}
        if settings.DEBUG and reset_url:
            payload["reset_url"] = reset_url
        return Response(payload, status=status.HTTP_200_OK)


class PasswordResetConfirmAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uidb64 = serializer.validated_data["uid"]
        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        User = get_user_model()
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except Exception:
            return Response(
                {"detail": "Invalid reset credentials."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not default_token_generator.check_token(user, token):
            return Response(
                {"detail": "Invalid or expired reset token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(new_password, user=user)
        except DjangoValidationError as exc:
            return Response(
                {"detail": {"new_password": exc.messages}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])
        return Response({"detail": "Password updated."}, status=status.HTTP_200_OK)


class AuthenticatedUserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = CompanyMembership.objects.filter(
            user=request.user,
            is_active=True,
        ).select_related("company")

        return Response(
            {
                "id": request.user.id,
                "username": request.user.username,
                "email": request.user.email,
                "is_staff": request.user.is_staff,
                "is_superuser": request.user.is_superuser,
                "platform_admin": request.user.is_staff or request.user.is_superuser,
                "memberships": [
                    {
                        "company_id": membership.company_id,
                        "company_name": membership.company.name,
                        "tenant_code": membership.company.tenant_code,
                        "role": membership.role,
                    }
                    for membership in memberships
                ],
            }
        )


class ActiveTenantUserAPIView(APIView):
    permission_classes = [IsAuthenticatedTenantMember]

    def get(self, request):
        membership = (
            CompanyMembership.objects.filter(
                company=request.company,
                user=request.user,
                is_active=True,
            )
            .select_related("company")
            .first()
        )
        return Response(
            {
                "user_id": request.user.id,
                "username": request.user.username,
                "company_id": request.company.id,
                "tenant_code": request.company.tenant_code,
                "role": membership.role if membership else None,
            }
        )


class TenantCapabilitiesAPIView(APIView):
    permission_classes = [IsAuthenticatedTenantMember]

    def get(self, request):
        membership = getattr(request, "tenant_membership", None)
        if membership is None:
            membership = (
                CompanyMembership.objects.filter(
                    company=request.company,
                    user=request.user,
                    is_active=True,
                )
                .only("role")
                .first()
            )

        role = membership.role if membership else None
        resource_matrices = get_resource_role_matrices(company=request.company)
        capabilities = {
            resource: resource_capabilities_for_role(role_matrix, role)
            for resource, role_matrix in resource_matrices.items()
        }

        return Response(
            {
                "tenant_code": request.company.tenant_code,
                "role": role,
                "capabilities": capabilities,
            }
        )


class TenantRBACAPIView(APIView):
    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticatedTenantMember()]
        return [IsTenantOwner()]

    def get(self, request):
        return Response(self._build_payload(request.company))

    def put(self, request):
        try:
            normalized_overrides = self._extract_and_validate_overrides(request.data)
        except ValidationError as exc:
            return Response(
                {"detail": self._validation_detail(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.company.rbac_overrides = normalized_overrides
        request.company.save(update_fields=["rbac_overrides", "updated_at"])
        return Response(self._build_payload(request.company))

    def patch(self, request):
        try:
            normalized_overrides = self._extract_and_validate_overrides(request.data)
            merged_overrides = self._merge_overrides(
                request.company.rbac_overrides,
                normalized_overrides,
            )
            validate_rbac_overrides_schema(merged_overrides)
            merged_overrides = normalize_rbac_overrides(merged_overrides)
        except ValidationError as exc:
            return Response(
                {"detail": self._validation_detail(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.company.rbac_overrides = merged_overrides
        request.company.save(update_fields=["rbac_overrides", "updated_at"])
        return Response(self._build_payload(request.company))

    @staticmethod
    def _merge_overrides(current_overrides, incoming_overrides):
        merged = deepcopy(current_overrides if isinstance(current_overrides, dict) else {})
        for resource_key, method_map in incoming_overrides.items():
            current_method_map = merged.get(resource_key, {})
            if not isinstance(current_method_map, dict):
                current_method_map = {}
            merged[resource_key] = {**current_method_map, **method_map}
        return merged

    @staticmethod
    def _extract_and_validate_overrides(payload):
        if not isinstance(payload, dict):
            raise ValidationError("Request body must be a JSON object.")

        raw_overrides = payload.get("rbac_overrides", payload)
        if raw_overrides in (None, ""):
            raw_overrides = {}

        validate_rbac_overrides_schema(raw_overrides)
        return normalize_rbac_overrides(raw_overrides)

    @staticmethod
    def _validation_detail(exception):
        try:
            return exception.message_dict
        except (AttributeError, TypeError):
            return exception.messages

    @staticmethod
    def _build_payload(company):
        tenant_overrides = normalize_rbac_overrides(getattr(company, "rbac_overrides", {}))
        effective_matrices = serialize_role_matrices(
            get_resource_role_matrices(company=company)
        )
        return {
            "tenant_code": company.tenant_code,
            "rbac_overrides": tenant_overrides,
            "effective_role_matrices": effective_matrices,
        }


class TenantEmailConfigAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "tenant.email.manage"

    def get(self, request):
        config = TenantEmailConfig.objects.filter(company=request.company).first()
        if config is None:
            return Response({"tenant_code": request.company.tenant_code, "config": None})
        return Response(
            {
                "tenant_code": request.company.tenant_code,
                "config": TenantEmailConfigSerializer(config).data,
            }
        )

    def post(self, request):
        config = TenantEmailConfig.objects.filter(company=request.company).first()
        serializer = TenantEmailConfigSerializer(
            instance=config,
            data=request.data,
            partial=config is not None,
        )
        serializer.is_valid(raise_exception=True)
        saved = serializer.save(company=request.company)
        return Response(
            {
                "tenant_code": request.company.tenant_code,
                "config": TenantEmailConfigSerializer(saved).data,
            },
            status=status.HTTP_201_CREATED if config is None else status.HTTP_200_OK,
        )


class TenantEmailConfigTestAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "tenant.email.manage"

    def post(self, request):
        config = TenantEmailConfig.objects.filter(company=request.company).first()
        if config is None:
            return Response(
                {"detail": "Tenant email config not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = TenantEmailConfigTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        to_email = (
            serializer.validated_data.get("to_email")
            or request.user.email
            or config.reply_to_email
            or config.default_from_email
        )
        if not to_email:
            return Response(
                {"detail": "Provide to_email or set a user email/default sender email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = EmailService()
        try:
            service.send_email(
                company=request.company,
                to_list=[to_email],
                subject="Teste de configuracao SMTP",
                text=(
                    "Este e um email de teste da configuracao SMTP do tenant "
                    f"{request.company.tenant_code}."
                ),
                html=(
                    "<p>Este e um email de teste da configuracao SMTP do tenant "
                    f"<strong>{request.company.tenant_code}</strong>.</p>"
                ),
            )
        except TenantEmailServiceError as exc:
            config.last_tested_at = timezone.now()
            config.last_test_status = TenantEmailConfig.TEST_STATUS_FAILED
            config.save(update_fields=["last_tested_at", "last_test_status", "updated_at"])
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            config.last_tested_at = timezone.now()
            config.last_test_status = TenantEmailConfig.TEST_STATUS_FAILED
            config.save(update_fields=["last_tested_at", "last_test_status", "updated_at"])
            return Response(
                {"detail": "Failed to send test email with the tenant SMTP configuration."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        config.last_tested_at = timezone.now()
        config.last_test_status = TenantEmailConfig.TEST_STATUS_SUCCESS
        config.save(update_fields=["last_tested_at", "last_test_status", "updated_at"])

        return Response(
            {
                "detail": "Test email sent.",
                "tenant_code": request.company.tenant_code,
                "to_email": to_email,
                "last_tested_at": config.last_tested_at,
                "last_test_status": config.last_test_status,
            }
        )


class TenantMembersAPIView(APIView):
    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticatedTenantMember()]
        return [IsTenantOwner()]

    def get(self, request):
        memberships = (
            CompanyMembership.objects.filter(
                company=request.company,
            )
            .select_related("user")
            .order_by("user__username")
        )
        serializer = CompanyMembershipReadSerializer(memberships, many=True)
        return Response(
            {
                "tenant_code": request.company.tenant_code,
                "results": serializer.data,
            }
        )

    def post(self, request):
        serializer = CompanyMembershipUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"]
        role = serializer.validated_data["role"]
        is_active = serializer.validated_data["is_active"]

        User = get_user_model()
        user = User.objects.filter(username=username).only("id").first()
        if user is None:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        membership, created = CompanyMembership.objects.update_or_create(
            company=request.company,
            user=user,
            defaults={"role": role, "is_active": is_active},
        )
        read_serializer = CompanyMembershipReadSerializer(membership)
        return Response(
            read_serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class TenantMemberDetailAPIView(APIView):
    permission_classes = [IsTenantOwner]

    def patch(self, request, membership_id):
        membership = get_object_or_404(
            CompanyMembership.objects.select_related("user"),
            id=membership_id,
            company=request.company,
        )
        serializer = CompanyMembershipUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role = serializer.validated_data.get("role", membership.role)
        is_active = serializer.validated_data.get("is_active", membership.is_active)

        if membership.user_id == request.user.id:
            if role != CompanyMembership.ROLE_OWNER:
                return Response(
                    {"detail": "Owner cannot downgrade their own role."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not is_active:
                return Response(
                    {"detail": "Owner cannot deactivate their own membership."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        membership.role = role
        membership.is_active = is_active
        membership.save(update_fields=["role", "is_active", "updated_at"])

        return Response(CompanyMembershipReadSerializer(membership).data)

    def delete(self, request, membership_id):
        membership = get_object_or_404(
            CompanyMembership.objects.select_related("user"),
            id=membership_id,
            company=request.company,
        )
        if membership.user_id == request.user.id:
            return Response(
                {"detail": "Owner cannot remove their own membership."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership.is_active = False
        membership.save(update_fields=["is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class TenantProducersAPIView(APIView):
    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticatedTenantMember()]
        return [IsTenantOwner()]

    def get(self, request):
        queryset = (
            ProducerProfile.objects.filter(company=request.company)
            .select_related("membership", "membership__user")
            .order_by("team_name", "full_name")
        )
        serializer = ProducerProfileReadSerializer(queryset, many=True)
        return Response(
            {
                "tenant_code": request.company.tenant_code,
                "results": serializer.data,
            }
        )

    def post(self, request):
        serializer = ProducerProfileUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        username = payload["username"]
        email = payload.get("email", "")

        User = get_user_model()
        user, _created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": payload["full_name"].split(" ", 1)[0],
                "last_name": payload["full_name"].split(" ", 1)[1] if " " in payload["full_name"] else "",
                "is_active": True,
            },
        )
        if email and not user.email:
            user.email = email
            user.save(update_fields=["email"])

        membership, _ = CompanyMembership.objects.update_or_create(
            company=request.company,
            user=user,
            defaults={
                "role": payload.get("role", CompanyMembership.ROLE_MEMBER),
                "is_active": payload.get("is_active", True),
            },
        )

        profile_defaults = {
            "full_name": payload["full_name"],
            "cpf": payload["cpf"],
            "team_name": payload.get("team_name", ""),
            "is_team_manager": payload.get("is_team_manager", False),
            "zip_code": payload.get("zip_code", ""),
            "state": payload.get("state", ""),
            "city": payload.get("city", ""),
            "neighborhood": payload.get("neighborhood", ""),
            "street": payload.get("street", ""),
            "street_number": payload.get("street_number", ""),
            "address_complement": payload.get("address_complement", ""),
            "commission_transfer_percent": payload["commission_transfer_percent"],
            "payout_hold_days": payload.get("payout_hold_days", 3),
            "bank_code": payload.get("bank_code", ""),
            "bank_name": payload.get("bank_name", ""),
            "bank_agency": payload.get("bank_agency", ""),
            "bank_account": payload.get("bank_account", ""),
            "bank_account_type": payload.get("bank_account_type", ""),
            "pix_key_type": payload.get("pix_key_type", ""),
            "pix_key": payload.get("pix_key", ""),
            "is_active": payload.get("is_active", True),
        }
        profile, created = ProducerProfile.objects.update_or_create(
            company=request.company,
            membership=membership,
            defaults=profile_defaults,
        )
        return Response(
            ProducerProfileReadSerializer(profile).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class TenantProducerDetailAPIView(APIView):
    permission_classes = [IsTenantOwner]

    def patch(self, request, producer_id):
        profile = get_object_or_404(
            ProducerProfile.objects.select_related("membership", "membership__user"),
            id=producer_id,
            company=request.company,
        )
        serializer = ProducerProfilePatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        if "role" in payload:
            profile.membership.role = payload["role"]
        if "is_active" in payload:
            profile.membership.is_active = payload["is_active"]
            profile.is_active = payload["is_active"]
        profile.membership.save(update_fields=["role", "is_active", "updated_at"])

        for field in (
            "full_name",
            "team_name",
            "is_team_manager",
            "zip_code",
            "state",
            "city",
            "neighborhood",
            "street",
            "street_number",
            "address_complement",
            "commission_transfer_percent",
            "payout_hold_days",
            "bank_code",
            "bank_name",
            "bank_agency",
            "bank_account",
            "bank_account_type",
            "pix_key_type",
            "pix_key",
            "is_active",
        ):
            if field in payload:
                setattr(profile, field, payload[field])
        profile.save()
        return Response(ProducerProfileReadSerializer(profile).data)


class TenantProducerPerformanceAPIView(APIView):
    permission_classes = [IsAuthenticatedTenantMember]

    def get(self, request):
        today = timezone.localdate()
        month_start = date(today.year, today.month, 1)
        if today.month == 12:
            next_month_start = date(today.year + 1, 1, 1)
        else:
            next_month_start = date(today.year, today.month + 1, 1)

        goal = (
            SalesGoal.all_objects.filter(
                company=request.company,
                year=today.year,
                month=today.month,
            )
            .order_by("-id")
            .first()
        )
        company_goal = goal.commission_goal if goal else Decimal("0.00")

        producers = list(
            ProducerProfile.objects.filter(
                company=request.company,
                is_active=True,
                membership__is_active=True,
            )
            .select_related("membership", "membership__user")
            .order_by("team_name", "full_name")
        )

        payables = (
            Payable.all_objects.filter(
                company=request.company,
                source_ref__startswith="PRODUCER_REPASSE:",
                due_date__gte=month_start,
                due_date__lt=next_month_start,
            )
            .select_related("recipient")
            .order_by("due_date")
        )

        by_user_id: dict[int, Decimal] = {}
        team_totals: dict[str, Decimal] = {}
        for payable in payables:
            if payable.recipient_id is None:
                continue
            by_user_id[payable.recipient_id] = by_user_id.get(payable.recipient_id, Decimal("0.00")) + (
                payable.amount or Decimal("0.00")
            )

        producer_rows = []
        for producer in producers:
            user_id = producer.membership.user_id
            result_value = by_user_id.get(user_id, Decimal("0.00"))
            team_name = producer.team_name.strip() or "Equipe Geral"
            team_totals[team_name] = team_totals.get(team_name, Decimal("0.00")) + result_value
            producer_rows.append(
                {
                    "producer_id": producer.id,
                    "membership_id": producer.membership_id,
                    "user_id": user_id,
                    "username": producer.membership.user.username,
                    "full_name": producer.full_name,
                    "role": producer.membership.role,
                    "team_name": team_name,
                    "is_team_manager": producer.is_team_manager,
                    "commission_transfer_percent": str(producer.commission_transfer_percent),
                    "result_current_month": str(result_value),
                }
            )

        producer_count = len(producer_rows)
        target_per_producer = (
            (company_goal / producer_count).quantize(Decimal("0.01"))
            if producer_count > 0
            else Decimal("0.00")
        )
        total_result = sum((Decimal(row["result_current_month"]) for row in producer_rows), Decimal("0.00"))
        progress_pct = (
            float((total_result / company_goal) * Decimal("100.00"))
            if company_goal > 0
            else 0.0
        )

        teams_payload = []
        for team_name, team_total in sorted(team_totals.items(), key=lambda item: item[0]):
            rows = [row for row in producer_rows if row["team_name"] == team_name]
            manager = next((row for row in rows if row["is_team_manager"]), None)
            teams_payload.append(
                {
                    "team_name": team_name,
                    "manager": manager["full_name"] if manager else None,
                    "result_current_month": str(team_total),
                    "members": rows,
                }
            )

        return Response(
            {
                "period": {
                    "month": today.month,
                    "year": today.year,
                    "start_date": month_start.isoformat(),
                    "end_date_exclusive": next_month_start.isoformat(),
                },
                "team_vs_goal": {
                    "company_goal_commission": str(company_goal),
                    "team_result_current_month": str(total_result),
                    "target_per_producer": str(target_per_producer),
                    "progress_pct": round(progress_pct, 2),
                    "producer_count": producer_count,
                },
                "individual_results": producer_rows,
                "teams": teams_payload,
            }
        )


class BankCatalogAPIView(APIView):
    permission_classes = [IsAuthenticatedTenantMember]

    BANKS = [
        {"code": "001", "name": "Banco do Brasil"},
        {"code": "033", "name": "Santander"},
        {"code": "104", "name": "Caixa Econômica Federal"},
        {"code": "237", "name": "Bradesco"},
        {"code": "341", "name": "Itaú"},
        {"code": "748", "name": "Sicredi"},
        {"code": "756", "name": "Sicoob"},
        {"code": "077", "name": "Banco Inter"},
        {"code": "260", "name": "Nu Pagamentos (Nubank)"},
        {"code": "290", "name": "PagSeguro"},
        {"code": "323", "name": "Mercado Pago"},
    ]

    def get(self, _request):
        return Response({"results": self.BANKS})
