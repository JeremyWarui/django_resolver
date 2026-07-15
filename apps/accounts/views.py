"""Auth and user-management views — Phase 6 (SoT §5.1, §3.8, R17)."""

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import RoleAssignment, UserProfile
from apps.accounts.serializers import (
    RoleAssignmentSerializer,
    RoleAssignmentCreateSerializer,
    RoleAssignmentUpdateSerializer,
    UserAdminSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
)
from apps.accounts.jwt_utils import build_tokens_for_assignment, serialize_auth_user
from apps.common.permissions import get_request_role
from apps.realtime.ws_utils import emit_role_changed

REFRESH_COOKIE = "resolver_refresh"
COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days


def _set_refresh_cookie(response, refresh_token):
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=str(refresh_token),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=False,
    )


def _clear_refresh_cookie(response):
    response.delete_cookie(REFRESH_COOKIE)


def _get_active_assignment_from_request(request):
    """Resolve which RoleAssignment is currently active for this request's JWT."""
    ra_id = None
    try:
        if request.auth:
            ra_id = request.auth.get("role_assignment_id")
    except Exception:
        pass
    return resolve_active_assignment(request.user, ra_id)


class MeView(APIView):
    """GET /auth/me/ — profile + all role assignments (§5.1)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        active = _get_active_assignment_from_request(request)
        data = serialize_auth_user(request.user, active)
        return Response(data)


class SwitchRoleView(APIView):
    """POST /auth/switch-role/ — re-issue JWT for a different active assignment (§3.8, §3.6)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ra_id = request.data.get("roleAssignmentId")
        if ra_id is None:
            return Response(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "roleAssignmentId is required",
                    }
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        try:
            ra = RoleAssignment.objects.select_related(
                "section", "campus_department", "department"
            ).get(pk=ra_id)
        except RoleAssignment.DoesNotExist:
            return Response(
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Role assignment not found",
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if ra.user_id != request.user.pk:
            return Response(
                {
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "This role assignment does not belong to you",
                    }
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if not ra.is_active():
            return Response(
                {
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "This role assignment is not currently active",
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Blacklist existing refresh token.
        raw_refresh = request.COOKIES.get(REFRESH_COOKIE)
        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except TokenError:
                pass

        refresh, access = build_tokens_for_assignment(request.user, ra)
        response = Response(
            {
                "user": serialize_auth_user(request.user, ra),
                "accessToken": str(access),
            },
            status=status.HTTP_200_OK,
        )
        _set_refresh_cookie(response, refresh)
        return response


def _sync_org_scope(target, ra, old_primary):
    """Keep org-structural FKs (Section.hos, CampusDepartment.head_of_department,
    Department.manager_user) and the SectionTechnician link table in sync with
    RoleAssignment. scope.py's scoped_ticket_qs/scoped_section_qs read those
    directly for primary manager/hod/hos scope (and always for technician,
    primary or cover) -- NOT RoleAssignment -- so a promotion that only
    creates a RoleAssignment row is a silent no-op for the promoted user's
    actual access.
    """
    from apps.org.models import Section, CampusDepartment, Department, SectionTechnician

    # Forward: grant scope for the new assignment.
    if ra.role == "technician" and ra.section_id:
        # No primary/cover distinction for technician scope -- always sync.
        SectionTechnician.objects.get_or_create(user=target, section_id=ra.section_id)
    elif ra.role == "hos" and ra.is_primary and ra.section_id:
        Section.objects.filter(pk=ra.section_id).update(hos=target)
    elif ra.role == "hod" and ra.is_primary and ra.campus_department_id:
        CampusDepartment.objects.filter(pk=ra.campus_department_id).update(
            head_of_department=target
        )
    elif ra.role == "manager" and ra.is_primary and ra.department_id:
        Department.objects.filter(pk=ra.department_id).update(manager_user=target)

    # Backward: revoke stale scope left over from the just-demoted primary,
    # unless the new assignment already covers the identical scope (then
    # it's a harmless no-op -- the forward sync above already reset it).
    if old_primary is None:
        return
    if old_primary.role == "hos" and old_primary.section_id:
        if not (ra.role == "hos" and ra.section_id == old_primary.section_id):
            Section.objects.filter(pk=old_primary.section_id, hos=target).update(hos=None)
    elif old_primary.role == "hod" and old_primary.campus_department_id:
        if not (ra.role == "hod" and ra.campus_department_id == old_primary.campus_department_id):
            CampusDepartment.objects.filter(
                pk=old_primary.campus_department_id, head_of_department=target
            ).update(head_of_department=None)
    elif old_primary.role == "manager" and old_primary.department_id:
        if not (ra.role == "manager" and ra.department_id == old_primary.department_id):
            Department.objects.filter(
                pk=old_primary.department_id, manager_user=target
            ).update(manager_user=None)
    elif old_primary.role == "technician" and old_primary.section_id:
        if not (ra.role == "technician" and ra.section_id == old_primary.section_id):
            SectionTechnician.objects.filter(
                user=target, section_id=old_primary.section_id
            ).delete()


class UserRoleAssignmentListCreateView(generics.ListCreateAPIView):
    """GET + POST /users/{user_pk}/role-assignments/

    GET: list all assignments for the target user (admin sees all; HOD within scope).
    POST: HOD/admin can create cover assignments (never primary, assigned_by = requester).
    """

    permission_classes = [IsAuthenticated]
    serializer_class = RoleAssignmentSerializer
    pagination_class = None  # a user has only a handful of assignments; frontend expects a bare list

    def _get_target_user(self):
        from django.contrib.auth import get_user_model
        from django.shortcuts import get_object_or_404

        User = get_user_model()
        return get_object_or_404(User, pk=self.kwargs["user_pk"])

    def _get_caller_role(self):
        return get_request_role(self.request)

    def get_queryset(self):
        target = self._get_target_user()
        caller_role = self._get_caller_role()
        qs = RoleAssignment.objects.filter(user=target).select_related(
            "section__campus_department__campus",
            "section__campus_department__department",
            "section__section_type",
            "campus_department__campus",
            "campus_department__department",
            "department",
            "assigned_by",
        )
        if caller_role == "admin":
            return qs
        if caller_role == "hod":
            # HOD sees only assignments scoped to sections within their campus_department.
            caller_ra = getattr(self.request.user, "primary_role_assignment", None)
            if caller_ra and caller_ra.campus_department_id:
                cd_id = caller_ra.campus_department_id
                return qs.filter(section__campus_department_id=cd_id) | qs.filter(
                    campus_department_id=cd_id
                )
        return RoleAssignment.objects.none()

    def create(self, request, *args, **kwargs):
        target = self._get_target_user()
        caller_role = self._get_caller_role()

        if caller_role not in ("admin", "hod"):
            return Response(
                {"detail": "Only HOD or admin may create role assignments."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = RoleAssignmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data

        # HOD scope check: can only assign roles within their campus_department.
        if caller_role == "hod":
            caller_ra = getattr(request.user, "primary_role_assignment", None)
            if caller_ra and caller_ra.campus_department_id:
                cd_id = caller_ra.campus_department_id
                section = vd.get("section")
                cd = vd.get("campus_department")
                section_cd_id = section.campus_department_id if section else None
                assignment_cd_id = cd.id if cd else None
                if section_cd_id != cd_id and assignment_cd_id != cd_id:
                    return Response(
                        {
                            "detail": "HOD can only create assignments within their campus department."
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
            if vd.get("role") not in ("technician", "hos"):
                return Response(
                    {
                        "detail": "HOD can only create technician or HOS cover assignments."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            vd["is_primary"] = False  # HOD can only create cover assignments

        is_primary = (
            vd.pop("is_primary", False)
            if caller_role == "admin"
            else (vd.pop("is_primary", None) or False)
        )

        # Strip the frontend-friendly keys before creating (already resolved to FK objects)
        vd.pop("campus_id", None)
        vd.pop("department_id", None)
        vd.pop("section_id", None)

        from django.db import IntegrityError, transaction

        try:
            with transaction.atomic():
                old_primary = None
                if is_primary:
                    # Replacing the primary role (e.g. promoting/demoting a user from
                    # the Users admin page) — demote the existing primary instead of
                    # erroring, since only one primary assignment is allowed per user.
                    old_primary = target.role_assignments.filter(
                        is_primary=True
                    ).select_related("section", "campus_department", "department").first()
                    target.role_assignments.filter(is_primary=True).update(
                        is_primary=False
                    )
                ra = RoleAssignment.objects.create(
                    user=target,
                    is_primary=is_primary,
                    assigned_by=request.user,
                    **vd,
                )
                _sync_org_scope(target, ra, old_primary)
                if is_primary:
                    # A primary swap is the one case that changes what the
                    # target's *current* session is authorized to do — cover
                    # (is_primary=False) assignments don't take effect until
                    # the user explicitly switches into them, so no push there.
                    transaction.on_commit(
                        lambda: emit_role_changed(
                            target.id,
                            old_primary.role if old_primary else None,
                            ra.role,
                        )
                    )
        except IntegrityError as exc:
            msg = str(exc)
            if "one_primary_role_per_user" in msg:
                return Response(
                    {
                        "detail": "This user already has a primary role assignment. Delete or demote it first, or set is_primary=false."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            raise
        ra = RoleAssignment.objects.select_related(
            "section__campus_department__campus",
            "section__campus_department__department",
            "section__section_type",
            "campus_department__campus",
            "campus_department__department",
            "department",
            "assigned_by",
        ).get(pk=ra.pk)
        return Response(
            RoleAssignmentSerializer(ra).data, status=status.HTTP_201_CREATED
        )


class UserRoleAssignmentDetailView(APIView):
    """PATCH + DELETE /users/{user_pk}/role-assignments/{ra_pk}/

    PATCH: update valid_until (HOD/admin within scope).
    DELETE: remove a cover assignment (HOD/admin within scope). Cannot delete primary.
    """

    permission_classes = [IsAuthenticated]

    def _get_objects(self):
        from django.contrib.auth import get_user_model
        from django.shortcuts import get_object_or_404

        User = get_user_model()
        target = get_object_or_404(User, pk=self.kwargs["user_pk"])
        ra = get_object_or_404(RoleAssignment, pk=self.kwargs["ra_pk"], user=target)
        return target, ra

    def _get_caller_role(self):
        return get_request_role(self.request)

    def _check_scope(self, ra):
        caller_role = self._get_caller_role()
        if caller_role == "admin":
            return True
        if caller_role == "hod":
            caller_ra = getattr(self.request.user, "primary_role_assignment", None)
            if caller_ra and caller_ra.campus_department_id:
                cd_id = caller_ra.campus_department_id
                if ra.section and ra.section.campus_department_id == cd_id:
                    return True
                if ra.campus_department_id == cd_id:
                    return True
        return False

    def patch(self, request, user_pk, ra_pk):
        _, ra = self._get_objects()
        if not self._check_scope(ra):
            return Response(
                {"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN
            )
        serializer = RoleAssignmentUpdateSerializer(ra, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # valid_until edits can end an actively-used cover assignment early —
        # push a signal so a session currently riding this assignment forces
        # a clean re-login instead of silently falling back to primary scope
        # with a UI still showing the (now invalid) cover role.
        emit_role_changed(ra.user_id, ra.role, ra.role)
        return Response(RoleAssignmentSerializer(ra).data)

    def delete(self, request, user_pk, ra_pk):
        _, ra = self._get_objects()
        if ra.is_primary:
            return Response(
                {"detail": "Cannot delete a primary role assignment."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not self._check_scope(ra):
            return Response(
                {"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN
            )
        ra.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Auth endpoints: login / refresh / logout ───────────────────────────────────
# Migrated from tickets/api/jwt_auth_views.py

import logging
from django.contrib.auth import authenticate, get_user_model
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken as _RefreshToken
from apps.accounts.jwt_utils import (
    get_primary_assignment_or_infer,
    ensure_floor_assignment,
    resolve_active_assignment,
)

_logger = logging.getLogger(__name__)
_User = get_user_model()


@api_view(["POST"])
@permission_classes([AllowAny])
def jwt_login(request):
    """POST /auth/login/ — password login, returns JWT access token + sets refresh cookie."""
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "username and password are required",
                }
            },
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    user = authenticate(username=username, password=password)
    if not user:
        return Response(
            {"error": {"code": "UNAUTHORIZED", "message": "Invalid credentials"}},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    assignment = get_primary_assignment_or_infer(user)
    refresh, access = build_tokens_for_assignment(user, assignment)

    response = Response(
        {
            "user": serialize_auth_user(user, assignment),
            "accessToken": str(access),
        },
        status=status.HTTP_200_OK,
    )
    _set_refresh_cookie(response, refresh)
    return response


@api_view(["GET"])
@permission_classes([AllowAny])
def public_campus_list(request):
    """GET /auth/campuses/ — minimal campus list for the public registration form.
    Unlike /api/v1/campuses/ (admin-only), this is intentionally public: a new
    registrant has no JWT yet and must pick their campus before an account exists."""
    from apps.org.models import Campus

    data = list(Campus.objects.order_by("name").values("id", "name", "code"))
    return Response(data)


@api_view(["POST"])
@permission_classes([AllowAny])
def jwt_register(request):
    """POST /auth/register/ — create account, auto-assign user floor role, return JWT."""
    username = request.data.get("username", "").strip()
    email = request.data.get("email", "").strip()
    password = request.data.get("password", "")
    first_name = request.data.get("first_name", "").strip()
    last_name = request.data.get("last_name", "").strip()
    campus_id = request.data.get("campus_id")

    if not first_name or not last_name or not email or not password or not campus_id:
        return Response(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "first_name, last_name, email, password and campus_id are required",
                }
            },
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if username and _User.objects.filter(username=username).exists():
        return Response(
            {"error": {"code": "CONFLICT", "message": "Username already taken"}},
            status=status.HTTP_409_CONFLICT,
        )
    if _User.objects.filter(email=email).exists():
        return Response(
            {"error": {"code": "CONFLICT", "message": "Email already registered"}},
            status=status.HTTP_409_CONFLICT,
        )

    from apps.org.models import Campus

    if not Campus.objects.filter(pk=campus_id).exists():
        return Response(
            {"error": {"code": "VALIDATION_ERROR", "message": "Campus not found"}},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    if not username:
        base = f"{first_name.lower()}.{last_name.lower()}"
        username = base
        n = 1
        while _User.objects.filter(username=username).exists():
            username = f"{base}{n}"
            n += 1

    user = _User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
    ensure_floor_assignment(user)
    UserProfile.objects.create(user=user, campus_id=campus_id)

    assignment = get_primary_assignment_or_infer(user)
    refresh, access = build_tokens_for_assignment(user, assignment)

    response = Response(
        {
            "user": serialize_auth_user(user, assignment),
            "accessToken": str(access),
        },
        status=status.HTTP_201_CREATED,
    )
    _set_refresh_cookie(response, refresh)
    return response


@api_view(["POST"])
@permission_classes([AllowAny])
def jwt_refresh(request):
    """POST /auth/refresh/ — rotate refresh token, return new access token."""
    raw_refresh = request.COOKIES.get(REFRESH_COOKIE)
    if not raw_refresh:
        return Response(
            {"error": {"code": "UNAUTHORIZED", "message": "No refresh token"}},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        refresh = _RefreshToken(raw_refresh)
        refresh.verify()

        # Rotate: blacklist old, issue new pair scoped to the user's *current*
        # role assignment — not a copy of the old token's claims — so a
        # promotion/demotion is picked up on the very next silent refresh
        # instead of persisting stale scope for up to REFRESH_TOKEN_LIFETIME.
        refresh.blacklist()
        uid_claim = _get_user_id_claim()
        user = _User.objects.get(pk=refresh[uid_claim])
        old_role = refresh.payload.get("role")
        active_assignment = resolve_active_assignment(
            user, refresh.payload.get("role_assignment_id")
        )
        new_refresh, new_access = build_tokens_for_assignment(user, active_assignment)
        new_role = active_assignment.role if active_assignment else None

    except Exception as exc:
        _logger.debug("jwt_refresh failed: %s", exc)
        return Response(
            {
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Invalid or expired refresh token",
                }
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # roleChanged tells the frontend its cached user object (role, sidebar,
    # dashboard choice — all set at login/switch-role time, never touched by
    # a silent refresh) is now stale, so it should force a clean re-login
    # rather than keep serving a UI built for the old role.
    response = Response(
        {"accessToken": str(new_access), "roleChanged": old_role != new_role},
        status=status.HTTP_200_OK,
    )
    _set_refresh_cookie(response, new_refresh)
    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def jwt_logout(request):
    """POST /auth/logout/ — blacklist refresh token, clear cookie."""
    raw_refresh = request.COOKIES.get(REFRESH_COOKIE)
    if raw_refresh:
        try:
            _RefreshToken(raw_refresh).blacklist()
        except Exception:
            pass

    response = Response(status=status.HTTP_204_NO_CONTENT)
    _clear_refresh_cookie(response)
    return response


def _get_user_id_claim():
    try:
        from rest_framework_simplejwt.settings import api_settings

        return api_settings.USER_ID_CLAIM
    except Exception:
        return "sub"


# ── Admin: user CRUD ──────────────────────────────────────────────────────────


class UserListCreateView(APIView):
    """GET + POST /api/v1/users/ — admin-only user management."""

    permission_classes = [IsAuthenticated]

    def _require_admin(self, request):
        if get_request_role(request) != "admin":
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Only admins may manage users.")

    def get(self, request):
        self._require_admin(request)
        from django.contrib.auth import get_user_model
        from django.db.models import Prefetch

        User = get_user_model()
        qs = User.objects.select_related("profile__campus").prefetch_related(
            Prefetch(
                "role_assignments",
                queryset=RoleAssignment.objects.filter(is_primary=True).select_related(
                    "section__campus_department__campus",
                    "section__campus_department__department",
                    "section__section_type",
                    "campus_department__campus",
                    "campus_department__department",
                    "department",
                ),
                to_attr="primary_ra_list",
            )
        ).order_by("-date_joined")

        serializer = UserAdminSerializer(qs, many=True)
        return Response(
            {
                "count": qs.count(),
                "next": None,
                "previous": None,
                "results": serializer.data,
            }
        )

    def post(self, request):
        self._require_admin(request)
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            UserAdminSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


class UserDetailView(APIView):
    """PATCH + DELETE /api/v1/users/<pk>/ — admin-only."""

    permission_classes = [IsAuthenticated]

    def _require_admin(self, request):
        if get_request_role(request) != "admin":
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Only admins may manage users.")

    def _get_user(self, pk):
        from django.contrib.auth import get_user_model
        from django.shortcuts import get_object_or_404

        return get_object_or_404(get_user_model(), pk=pk)

    def patch(self, request, pk):
        self._require_admin(request)
        user = self._get_user(pk)
        serializer = UserUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserAdminSerializer(user).data)

    def delete(self, request, pk):
        self._require_admin(request)
        user = self._get_user(pk)
        if user == request.user:
            return Response(
                {"detail": "You cannot delete your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
