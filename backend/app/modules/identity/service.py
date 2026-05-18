from datetime import UTC, datetime
from shlex import quote
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.identity.models import (
    IdentityExecution,
    IdentityExecutionStatus,
    LinuxGroup,
    LinuxUser,
    PermissionTemplate,
    SSHKey,
)
from backend.app.modules.identity.repository import (
    IdentityExecutionRepository,
    LinuxGroupRepository,
    LinuxUserRepository,
    PermissionTemplateRepository,
    SSHKeyRepository,
)
from backend.app.modules.identity.schemas import (
    AccessProfileRead,
    DiscoveredGroupRead,
    DiscoveredUserRead,
    GroupMembersRequest,
    GroupDiscoveryRead,
    GroupMemberHostRead,
    GroupMembershipRead,
    GroupPresetRead,
    IdentityMutationRead,
    IdentityReplicationRead,
    LinuxGroupCreate,
    LinuxGroupRead,
    LinuxGroupUpdate,
    LinuxUserCreate,
    LinuxUserRead,
    LinuxUserUpdate,
    PermissionApplyRequest,
    PermissionPresetRead,
    PermissionReplicateRequest,
    PermissionTemplateCreate,
    PermissionTemplateRead,
    ReplicationRequest,
    SSHKeyCreate,
    SSHKeyDeployRequest,
    SSHKeyRead,
    UserDiscoveryRead,
    UserGroupMembershipHostRead,
    UserGroupMembershipRead,
    GROUP_PATTERN,
    USERNAME_PATTERN,
)
from backend.app.modules.jobs.models import JobStatus
from backend.app.modules.jobs.schemas import BulkExecutionHostResult, JobBulkExecuteRequest
from backend.app.modules.jobs.service import JobService


class IdentityNotFoundError(Exception):
    """Raised when an identity object cannot be found."""


class IdentityConflictError(Exception):
    """Raised when an identity object already exists."""


class IdentityValidationError(Exception):
    """Raised when an identity operation is invalid."""


class IdentityPresetService:
    """Friendly operational identity presets layered over Linux primitives."""

    def list_access_profiles(self) -> list[AccessProfileRead]:
        return [
            AccessProfileRead(
                id="standard-user",
                name="Standard User",
                description="Interactive user without elevated privileges.",
                shell="/bin/bash",
                sudo_enabled=False,
                sudo_nopasswd=False,
                supplementary_groups=[],
            ),
            AccessProfileRead(
                id="administrator",
                name="Administrator",
                description="Elevated access using the distro admin group and sudoers.d.",
                shell="/bin/bash",
                sudo_enabled=True,
                sudo_nopasswd=False,
                supplementary_groups=["__admin__"],
            ),
            AccessProfileRead(
                id="deployment-operator",
                name="Deployment Operator",
                description="Operational user for application deployments.",
                shell="/bin/bash",
                sudo_enabled=True,
                sudo_nopasswd=False,
                supplementary_groups=["docker", "www-data"],
                permission_presets=["application-directory"],
            ),
            AccessProfileRead(
                id="docker-operator",
                name="Docker Operator",
                description="Allows Docker and Compose management through the docker group.",
                shell="/bin/bash",
                sudo_enabled=False,
                sudo_nopasswd=False,
                supplementary_groups=["docker"],
            ),
            AccessProfileRead(
                id="log-viewer",
                name="Log Viewer",
                description="Read operational logs without broad admin rights.",
                shell="/bin/bash",
                sudo_enabled=False,
                sudo_nopasswd=False,
                supplementary_groups=["adm", "systemd-journal"],
            ),
            AccessProfileRead(
                id="read-only",
                name="Read Only",
                description="Interactive access with no elevated privileges.",
                shell="/bin/bash",
                sudo_enabled=False,
                sudo_nopasswd=False,
                supplementary_groups=[],
            ),
            AccessProfileRead(
                id="service-account",
                name="Service Account",
                description="Non-interactive account for services and automation.",
                shell="/usr/sbin/nologin",
                sudo_enabled=False,
                sudo_nopasswd=False,
                supplementary_groups=[],
            ),
            AccessProfileRead(
                id="custom",
                name="Custom",
                description="Expose advanced Linux controls.",
                shell="/bin/bash",
                sudo_enabled=False,
                sudo_nopasswd=False,
                supplementary_groups=[],
                advanced=True,
            ),
        ]

    def list_group_presets(self) -> list[GroupPresetRead]:
        return [
            GroupPresetRead(id="docker", name="Docker Operators", group="docker", description="Allows Docker socket and Compose operations.", recommended_for="Docker and deployment operators", distro_families=["debian", "rhel"]),
            GroupPresetRead(id="admin", name="Administrator Access", group="__admin__", description="Resolves to sudo on Debian/Ubuntu and wheel on RHEL-like systems.", recommended_for="Administrators", distro_families=["debian", "rhel"]),
            GroupPresetRead(id="adm", name="System Log Readers", group="adm", description="Allows access to many system logs on Debian-like systems.", recommended_for="Log viewers", distro_families=["debian"]),
            GroupPresetRead(id="systemd-journal", name="Journal Readers", group="systemd-journal", description="Allows reading systemd journal logs.", recommended_for="Log viewers", distro_families=["debian", "rhel"]),
            GroupPresetRead(id="www-data", name="Web Runtime", group="www-data", description="Common web server runtime group.", recommended_for="Application operators", distro_families=["debian"]),
            GroupPresetRead(id="libvirt", name="Virtualization Operators", group="libvirt", description="Allows libvirt virtualization management where available.", recommended_for="Virtualization operators", distro_families=["debian", "rhel"]),
        ]

    def list_permission_presets(self) -> list[PermissionPresetRead]:
        return [
            PermissionPresetRead(id="private-directory", name="Private Directory", mode="0700", description="Owner-only directory access."),
            PermissionPresetRead(id="application-directory", name="Application Directory", mode="0755", description="Owner can write; everyone can read and enter."),
            PermissionPresetRead(id="shared-team-directory", name="Shared Team Directory", mode="0775", description="Owner and group can collaborate; others can read and enter."),
            PermissionPresetRead(id="read-only-file", name="Read Only File", mode="0644", description="Owner can write; everyone can read."),
            PermissionPresetRead(id="executable-script", name="Executable Script", mode="0755", description="Script executable by everyone, writable by owner."),
            PermissionPresetRead(id="public-writable", name="Public Writable", mode="0777", description="Writable by everyone. Use only for temporary lab paths."),
            PermissionPresetRead(id="custom", name="Custom", mode="0755", description="Use the permission matrix or raw octal mode."),
        ]


class IdentityReplicationService:
    """Sequential multi-host identity fanout through the Jobs pipeline."""

    def __init__(self, *, job_service: JobService, execution_repository: IdentityExecutionRepository) -> None:
        self.job_service = job_service
        self.execution_repository = execution_repository

    async def replicate(
        self,
        *,
        target_server_ids: list[UUID],
        operation_type: str,
        command: str,
        redacted_command: str | None = None,
    ) -> IdentityReplicationRead:
        result = await self.job_service.execute_bulk(
            JobBulkExecuteRequest(
                target_server_ids=target_server_ids,
                operation_type=operation_type,
                command=command,
                redacted_command=redacted_command,
            )
        )

        persisted_results: list[BulkExecutionHostResult] = []
        for host_result in result.results:
            if host_result.job:
                execution = IdentityExecution(
                    operation_type=operation_type,
                    target_server_id=host_result.target_server_id,
                    job_id=host_result.job.id,
                    status=IdentityExecutionStatus.SUCCESS
                    if host_result.job.status == JobStatus.SUCCESS
                    else IdentityExecutionStatus.FAILED,
                    stdout=host_result.job.stdout,
                    stderr=host_result.job.stderr or host_result.error,
                    started_at=host_result.job.started_at,
                    completed_at=host_result.job.completed_at,
                )
            else:
                now = datetime.now(UTC)
                execution = IdentityExecution(
                    operation_type=operation_type,
                    target_server_id=host_result.target_server_id,
                    job_id=None,
                    status=IdentityExecutionStatus.FAILED,
                    stdout=None,
                    stderr=host_result.error,
                    started_at=now,
                    completed_at=now,
                )
            await self.execution_repository.create(execution)
            persisted_results.append(host_result)

        await self.execution_repository.session.commit()
        return IdentityReplicationRead(
            operation_type=result.operation_type,
            success_count=result.success_count,
            failure_count=result.failure_count,
            results=persisted_results,
        )

    async def discover_groups(self, target_server_ids: list[UUID]) -> GroupDiscoveryRead:
        result = await self.job_service.execute_bulk(
            JobBulkExecuteRequest(
                target_server_ids=target_server_ids,
                operation_type="identity:groups:discover",
                command="getent group",
            )
        )
        groups: dict[str, DiscoveredGroupRead] = {}
        for host_result in result.results:
            if not host_result.job or not host_result.job.stdout:
                continue
            hostname = host_result.target_hostname or str(host_result.target_server_id)
            for line in host_result.job.stdout.splitlines():
                parts = line.split(":")
                if len(parts) < 3 or not parts[0]:
                    continue
                try:
                    gid = int(parts[2])
                except ValueError:
                    gid = None
                existing = groups.get(parts[0])
                if existing is None:
                    groups[parts[0]] = DiscoveredGroupRead(
                        name=parts[0],
                        hosts=[hostname],
                        gid=gid,
                        members=sorted([member for member in parts[3].split(",") if member]) if len(parts) > 3 else [],
                    )
                elif hostname not in existing.hosts:
                    existing.hosts.append(hostname)
                    for member in parts[3].split(",") if len(parts) > 3 else []:
                        if member and member not in existing.members:
                            existing.members.append(member)
        return GroupDiscoveryRead(groups=sorted(groups.values(), key=lambda item: item.name))

    async def discover_group_members(self, group_name: str, target_server_ids: list[UUID]) -> GroupMembershipRead:
        if not GROUP_PATTERN.match(group_name):
            raise IdentityValidationError("Invalid Linux group name")
        result = await self.job_service.execute_bulk(
            JobBulkExecuteRequest(
                target_server_ids=target_server_ids,
                operation_type=f"identity:group:{group_name}:members:discover",
                command=f"getent group {quote(group_name)}; getent passwd",
            )
        )
        hosts = []
        for host_result in result.results:
            members: set[str] = set()
            primary_members: set[str] = set()
            supplementary_members: set[str] = set()
            error = host_result.error
            if host_result.job and host_result.job.stdout:
                lines = host_result.job.stdout.splitlines()
                group_gid = None
                for line in lines:
                    parts = line.split(":")
                    if len(parts) == 4 and parts[0] == group_name:
                        try:
                            group_gid = int(parts[2])
                        except ValueError:
                            group_gid = None
                        supplementary_members.update(member for member in parts[3].split(",") if member)
                        break
                if group_gid is None:
                    error = error or f"Group {group_name} was not found"
                for line in lines:
                    parts = line.split(":")
                    if len(parts) >= 7 and group_gid is not None:
                        try:
                            user_gid = int(parts[3])
                        except ValueError:
                            continue
                        if user_gid == group_gid:
                            primary_members.add(parts[0])
                members.update(primary_members)
                members.update(supplementary_members)
            elif host_result.job:
                error = host_result.job.stderr or error or "No group data returned"
            hosts.append(
                GroupMemberHostRead(
                    target_server_id=host_result.target_server_id,
                    target_hostname=host_result.target_hostname,
                    members=sorted(members),
                    primary_members=sorted(primary_members),
                    supplementary_members=sorted(supplementary_members),
                    error=error,
                )
            )
        return GroupMembershipRead(group=group_name, hosts=hosts)

    async def discover_users(self, target_server_ids: list[UUID]) -> UserDiscoveryRead:
        result = await self.job_service.execute_bulk(
            JobBulkExecuteRequest(
                target_server_ids=target_server_ids,
                operation_type="identity:users:discover",
                command="getent passwd",
            )
        )
        users: dict[str, DiscoveredUserRead] = {}
        for host_result in result.results:
            if not host_result.job or not host_result.job.stdout:
                continue
            hostname = host_result.target_hostname or str(host_result.target_server_id)
            for line in host_result.job.stdout.splitlines():
                parts = line.split(":")
                if len(parts) < 7 or not parts[0]:
                    continue
                try:
                    uid = int(parts[2])
                    gid = int(parts[3])
                except ValueError:
                    uid = None
                    gid = None
                if uid is not None and uid < 1000 and parts[0] != "root":
                    continue
                existing = users.get(parts[0])
                if existing is None:
                    users[parts[0]] = DiscoveredUserRead(
                        username=parts[0],
                        hosts=[hostname],
                        uid=uid,
                        gid=gid,
                        home_directory=parts[5] or None,
                        shell=parts[6] or None,
                    )
                elif hostname not in existing.hosts:
                    existing.hosts.append(hostname)
        return UserDiscoveryRead(users=sorted(users.values(), key=lambda item: item.username))

    async def discover_user_groups(self, username: str, target_server_ids: list[UUID]) -> UserGroupMembershipRead:
        if not USERNAME_PATTERN.match(username):
            raise IdentityValidationError("Invalid Linux username")
        result = await self.job_service.execute_bulk(
            JobBulkExecuteRequest(
                target_server_ids=target_server_ids,
                operation_type=f"identity:user:{username}:groups:discover",
                command=f"id -nG {quote(username)}",
            )
        )
        hosts = []
        for host_result in result.results:
            groups = []
            error = host_result.error
            if host_result.job:
                groups = sorted(set(host_result.job.stdout.split())) if host_result.job.stdout else []
                error = host_result.job.stderr or error
            hosts.append(
                UserGroupMembershipHostRead(
                    target_server_id=host_result.target_server_id,
                    target_hostname=host_result.target_hostname,
                    groups=groups,
                    error=error,
                )
            )
        return UserGroupMembershipRead(username=username, hosts=hosts)


class LinuxUserService:
    def __init__(
        self,
        *,
        repository: LinuxUserRepository,
        replication_service: IdentityReplicationService,
        credential_service: CredentialService | None = None,
    ) -> None:
        self.repository = repository
        self.replication_service = replication_service
        self.credential_service = credential_service

    async def list_users(self) -> list[LinuxUserRead]:
        return [LinuxUserRead.model_validate(user) for user in await self.repository.list()]

    async def create_user(self, payload: LinuxUserCreate) -> IdentityMutationRead:
        password_command, redacted_password_command = await self._password_commands(
            payload.username,
            payload.password_credential_ref if payload.target_server_ids else None,
        )
        user = LinuxUser(
            username=payload.username,
            shell=payload.shell,
            home_directory=payload.home_directory or f"/home/{payload.username}",
            sudo_enabled=payload.sudo_enabled,
            sudo_nopasswd=payload.sudo_nopasswd,
            locked=payload.locked,
            managed=payload.managed,
        )
        try:
            user = await self.repository.create(user)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            raise IdentityConflictError("Linux user already exists") from exc

        replication = None
        if payload.target_server_ids:
            command = self._create_user_command(user, supplementary_groups=payload.supplementary_groups)
            redacted_command = command
            if password_command and redacted_password_command:
                command = f"{command} && {password_command}"
                redacted_command = f"{redacted_command} && {redacted_password_command}"
            replication = await self.replication_service.replicate(
                target_server_ids=payload.target_server_ids,
                operation_type=f"identity:user:{user.username}:replicate",
                command=command,
                redacted_command=redacted_command,
            )
        return IdentityMutationRead(item=LinuxUserRead.model_validate(user), replication=replication)

    async def adopt_user(self, payload: LinuxUserCreate) -> IdentityMutationRead:
        existing = await self.repository.get_by_username(payload.username)
        if existing is not None:
            return IdentityMutationRead(item=LinuxUserRead.model_validate(existing), replication=None)
        user = LinuxUser(
            username=payload.username,
            shell=payload.shell,
            home_directory=payload.home_directory or f"/home/{payload.username}",
            sudo_enabled=payload.sudo_enabled,
            sudo_nopasswd=payload.sudo_nopasswd,
            locked=payload.locked,
            managed=payload.managed,
        )
        try:
            user = await self.repository.create(user)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            raise IdentityConflictError("Linux user already exists") from exc
        return IdentityMutationRead(item=LinuxUserRead.model_validate(user), replication=None)

    async def update_user(self, user_id: UUID, payload: LinuxUserUpdate) -> IdentityMutationRead:
        user = await self._user(user_id)
        password_command, redacted_password_command = await self._password_commands(
            user.username,
            payload.password_credential_ref if payload.target_server_ids else None,
        )
        user.shell = payload.shell
        user.home_directory = payload.home_directory or user.home_directory
        user.sudo_enabled = payload.sudo_enabled
        user.sudo_nopasswd = payload.sudo_nopasswd
        user.locked = payload.locked
        user.managed = payload.managed
        await self.repository.session.commit()
        await self.repository.session.refresh(user)

        replication = None
        if payload.target_server_ids:
            command = self._modify_user_command(user, supplementary_groups=payload.supplementary_groups)
            redacted_command = command
            if password_command and redacted_password_command:
                command = f"{command} && {password_command}"
                redacted_command = f"{redacted_command} && {redacted_password_command}"
            replication = await self.replication_service.replicate(
                target_server_ids=payload.target_server_ids,
                operation_type=f"identity:user:{user.username}:update",
                command=command,
                redacted_command=redacted_command,
            )
        return IdentityMutationRead(item=LinuxUserRead.model_validate(user), replication=replication)

    async def delete_user(self, user_id: UUID, target_server_ids: list[UUID] | None = None, *, remove_home: bool = False) -> None:
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise IdentityNotFoundError("Linux user not found")
        if target_server_ids:
            command = self._delete_user_command(user.username, remove_home=remove_home)
            await self.replication_service.replicate(
                target_server_ids=target_server_ids,
                operation_type=f"identity:user:{user.username}:delete",
                command=command,
            )
        await self.repository.delete(user)
        await self.repository.session.commit()

    async def lock_user(self, user_id: UUID, payload: ReplicationRequest) -> IdentityReplicationRead:
        user = await self._user(user_id)
        user.locked = True
        await self.repository.session.commit()
        return await self.replication_service.replicate(
            target_server_ids=payload.target_server_ids,
            operation_type=f"identity:user:{user.username}:lock",
            command=f"sudo passwd -l {quote(user.username)}",
        )

    async def unlock_user(self, user_id: UUID, payload: ReplicationRequest) -> IdentityReplicationRead:
        user = await self._user(user_id)
        user.locked = False
        await self.repository.session.commit()
        return await self.replication_service.replicate(
            target_server_ids=payload.target_server_ids,
            operation_type=f"identity:user:{user.username}:unlock",
            command=f"sudo passwd -u {quote(user.username)}",
        )

    async def replicate_user(self, user_id: UUID, payload: ReplicationRequest) -> IdentityReplicationRead:
        user = await self._user(user_id)
        return await self.replication_service.replicate(
            target_server_ids=payload.target_server_ids,
            operation_type=f"identity:user:{user.username}:replicate",
            command=self._create_user_command(user),
        )

    async def _user(self, user_id: UUID) -> LinuxUser:
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise IdentityNotFoundError("Linux user not found")
        return user

    def _create_user_command(
        self,
        user: LinuxUser,
        *,
        supplementary_groups: list[str] | None = None,
    ) -> str:
        pieces = [
            "if ! id -u {username} >/dev/null 2>&1; then sudo useradd -m -d {home} -s {shell} {username}; fi".format(
                username=quote(user.username),
                home=quote(user.home_directory),
                shell=quote(user.shell),
            )
        ]
        if user.locked:
            pieces.append(f"sudo passwd -l {quote(user.username)}")
        if user.sudo_enabled:
            pieces.append(self._sudo_command(user))
        group_command = self.supplementary_group_command(user.username, supplementary_groups or [])
        if group_command:
            pieces.append(group_command)
        return " && ".join(pieces)

    async def _password_commands(self, username: str, credential_ref: str | None) -> tuple[str | None, str | None]:
        if not credential_ref:
            return None, None
        if self.credential_service is None:
            raise IdentityValidationError("Credential service is not configured for password operations")
        credential = await self.credential_service.resolve_credential(credential_ref)
        if credential.credential_type not in {"password", "ssh_password"}:
            raise IdentityValidationError("Password credential must be a password or ssh_password type")
        if not credential.secret:
            raise IdentityValidationError("Password credential has no secret value")
        password_line = f"{username}:{credential.secret}"
        redacted_line = f"{username}:********"
        return (
            f"printf '%s\\n' {quote(password_line)} | sudo chpasswd",
            f"printf '%s\\n' {quote(redacted_line)} | sudo chpasswd",
        )

    def _modify_user_command(
        self,
        user: LinuxUser,
        *,
        supplementary_groups: list[str] | None = None,
    ) -> str:
        pieces = [
            f"if ! id -u {quote(user.username)} >/dev/null 2>&1; then "
            + self._create_user_command(user, supplementary_groups=supplementary_groups)
            + f"; else sudo usermod -s {quote(user.shell)} -d {quote(user.home_directory)} {quote(user.username)}; fi"
        ]
        if user.locked:
            pieces.append(f"sudo passwd -l {quote(user.username)}")
        else:
            pieces.append(f"sudo passwd -u {quote(user.username)} || true")
        if user.sudo_enabled:
            pieces.append(self._sudo_command(user))
        else:
            pieces.append(f"sudo rm -f {quote(f'/etc/sudoers.d/nexusops-{user.username}')}")
        group_command = self.supplementary_group_command(user.username, supplementary_groups or [])
        if group_command:
            pieces.append(group_command)
        return " && ".join(pieces)

    @staticmethod
    def supplementary_group_command(username: str, groups: list[str]) -> str | None:
        if not groups:
            return None
        commands = []
        for group in groups:
            if group == "__admin__":
                commands.append(
                    "admin_group=$(if grep -qiE 'debian|ubuntu' /etc/os-release; then echo sudo; else echo wheel; fi) "
                    f"&& if ! getent group \"$admin_group\" >/dev/null; then sudo groupadd \"$admin_group\"; fi "
                    f"&& sudo usermod -aG \"$admin_group\" {quote(username)}"
                )
            else:
                commands.append(
                    f"if ! getent group {quote(group)} >/dev/null; then sudo groupadd {quote(group)}; fi "
                    f"&& sudo usermod -aG {quote(group)} {quote(username)}"
                )
        return " && ".join(commands)

    @staticmethod
    def _delete_user_command(username: str, *, remove_home: bool) -> str:
        flag = "-r " if remove_home else ""
        return f"if id -u {quote(username)} >/dev/null 2>&1; then sudo userdel {flag}{quote(username)}; fi"

    @staticmethod
    def _sudo_command(user: LinuxUser) -> str:
        rule = "ALL=(ALL) NOPASSWD:ALL" if user.sudo_nopasswd else "ALL=(ALL) ALL"
        path = f"/etc/sudoers.d/nexusops-{user.username}"
        return (
            f"printf '%s\\n' {quote(f'{user.username} {rule}')} | sudo tee {quote(path)} >/dev/null "
            f"&& sudo chmod 440 {quote(path)} && sudo visudo -cf {quote(path)}"
        )


class LinuxGroupService:
    def __init__(
        self,
        *,
        repository: LinuxGroupRepository,
        replication_service: IdentityReplicationService,
    ) -> None:
        self.repository = repository
        self.replication_service = replication_service

    async def list_groups(self) -> list[LinuxGroupRead]:
        return [LinuxGroupRead.model_validate(group) for group in await self.repository.list()]

    async def create_group(self, payload: LinuxGroupCreate) -> IdentityMutationRead:
        group = LinuxGroup(name=payload.name, description=payload.description, managed=payload.managed)
        try:
            group = await self.repository.create(group)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            raise IdentityConflictError("Linux group already exists") from exc
        replication = None
        if payload.target_server_ids:
            replication = await self.replicate_group(group.id, ReplicationRequest(target_server_ids=payload.target_server_ids))
        return IdentityMutationRead(item=LinuxGroupRead.model_validate(group), replication=replication)

    async def adopt_group(self, payload: LinuxGroupCreate) -> IdentityMutationRead:
        existing = await self.repository.get_by_name(payload.name)
        if existing is not None:
            return IdentityMutationRead(item=LinuxGroupRead.model_validate(existing), replication=None)
        group = LinuxGroup(name=payload.name, description=payload.description, managed=payload.managed)
        try:
            group = await self.repository.create(group)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            raise IdentityConflictError("Linux group already exists") from exc
        return IdentityMutationRead(item=LinuxGroupRead.model_validate(group), replication=None)

    async def update_group(self, group_id: UUID, payload: LinuxGroupUpdate) -> IdentityMutationRead:
        group = await self._group(group_id)
        previous_name = group.name
        if payload.name != group.name:
            existing = await self.repository.get_by_name(payload.name)
            if existing and existing.id != group.id:
                raise IdentityConflictError("Linux group already exists")
        group.name = payload.name
        group.description = payload.description
        group.managed = payload.managed
        await self.repository.session.commit()
        await self.repository.session.refresh(group)

        replication = None
        if payload.target_server_ids:
            command = self._update_group_command(previous_name=previous_name, next_name=group.name)
            replication = await self.replication_service.replicate(
                target_server_ids=payload.target_server_ids,
                operation_type=f"identity:group:{group.name}:update",
                command=command,
            )
        return IdentityMutationRead(item=LinuxGroupRead.model_validate(group), replication=replication)

    async def delete_group(self, group_id: UUID, target_server_ids: list[UUID] | None = None) -> None:
        group = await self._group(group_id)
        if target_server_ids:
            await self.replication_service.replicate(
                target_server_ids=target_server_ids,
                operation_type=f"identity:group:{group.name}:delete",
                command=f"if getent group {quote(group.name)} >/dev/null; then sudo groupdel {quote(group.name)}; fi",
            )
        await self.repository.delete(group)
        await self.repository.session.commit()

    async def add_members(self, group_id: UUID, payload: GroupMembersRequest) -> IdentityReplicationRead:
        group = await self._group(group_id)
        command = " && ".join(
            f"sudo usermod -aG {quote(group.name)} {quote(username)}" for username in payload.usernames
        )
        return await self.replication_service.replicate(
            target_server_ids=payload.target_server_ids,
            operation_type=f"identity:group:{group.name}:members",
            command=command,
        )

    async def replicate_group(self, group_id: UUID, payload: ReplicationRequest) -> IdentityReplicationRead:
        group = await self._group(group_id)
        return await self.replication_service.replicate(
            target_server_ids=payload.target_server_ids,
            operation_type=f"identity:group:{group.name}:replicate",
            command=f"if ! getent group {quote(group.name)} >/dev/null; then sudo groupadd {quote(group.name)}; fi",
        )

    async def _group(self, group_id: UUID) -> LinuxGroup:
        group = await self.repository.get_by_id(group_id)
        if group is None:
            raise IdentityNotFoundError("Linux group not found")
        return group

    @staticmethod
    def _update_group_command(*, previous_name: str, next_name: str) -> str:
        if previous_name == next_name:
            return f"if ! getent group {quote(next_name)} >/dev/null; then sudo groupadd {quote(next_name)}; fi"
        return (
            f"if getent group {quote(previous_name)} >/dev/null; then "
            f"sudo groupmod -n {quote(next_name)} {quote(previous_name)}; "
            f"elif ! getent group {quote(next_name)} >/dev/null; then sudo groupadd {quote(next_name)}; fi"
        )


class LinuxSSHKeyService:
    def __init__(self, *, repository: SSHKeyRepository, replication_service: IdentityReplicationService) -> None:
        self.repository = repository
        self.replication_service = replication_service

    async def list_keys(self) -> list[SSHKeyRead]:
        return [SSHKeyRead.model_validate(key) for key in await self.repository.list()]

    async def create_key(self, payload: SSHKeyCreate) -> SSHKeyRead:
        key = await self.repository.create(
            SSHKey(name=payload.name, public_key=payload.public_key, description=payload.description)
        )
        await self.repository.session.commit()
        return SSHKeyRead.model_validate(key)

    async def deploy_key(self, key_id: UUID, payload: SSHKeyDeployRequest) -> IdentityReplicationRead:
        key = await self._key(key_id)
        home = f"/home/{payload.username}"
        key_line = quote(key.public_key)
        command = (
            f"sudo install -d -m 700 -o {quote(payload.username)} -g {quote(payload.username)} {quote(home + '/.ssh')} "
            f"&& sudo touch {quote(home + '/.ssh/authorized_keys')} "
            f"&& grep -qxF {key_line} {quote(home + '/.ssh/authorized_keys')} || echo {key_line} | sudo tee -a {quote(home + '/.ssh/authorized_keys')} >/dev/null; "
            f"sudo chown {quote(payload.username)}:{quote(payload.username)} {quote(home + '/.ssh/authorized_keys')} "
            f"&& sudo chmod 600 {quote(home + '/.ssh/authorized_keys')}"
        )
        return await self.replication_service.replicate(
            target_server_ids=payload.target_server_ids,
            operation_type=f"identity:ssh-key:{key.name}:deploy",
            command=command,
        )

    async def revoke_key(self, key_id: UUID, payload: SSHKeyDeployRequest) -> IdentityReplicationRead:
        key = await self._key(key_id)
        auth_keys = f"/home/{payload.username}/.ssh/authorized_keys"
        command = (
            f"if test -f {quote(auth_keys)}; then "
            f"sudo sed -i {quote('/' + key.public_key.replace('/', r'\\/') + '/d')} {quote(auth_keys)}; "
            "fi"
        )
        return await self.replication_service.replicate(
            target_server_ids=payload.target_server_ids,
            operation_type=f"identity:ssh-key:{key.name}:revoke",
            command=command,
        )

    async def _key(self, key_id: UUID) -> SSHKey:
        key = await self.repository.get_by_id(key_id)
        if key is None:
            raise IdentityNotFoundError("SSH key not found")
        return key


class LinuxPermissionService:
    def __init__(
        self,
        *,
        repository: PermissionTemplateRepository,
        replication_service: IdentityReplicationService,
    ) -> None:
        self.repository = repository
        self.replication_service = replication_service

    async def list_templates(self) -> list[PermissionTemplateRead]:
        return [PermissionTemplateRead.model_validate(template) for template in await self.repository.list()]

    async def create_template(self, payload: PermissionTemplateCreate) -> PermissionTemplateRead:
        template = await self.repository.create(PermissionTemplate(**payload.model_dump()))
        await self.repository.session.commit()
        return PermissionTemplateRead.model_validate(template)

    async def apply(self, payload: PermissionApplyRequest) -> IdentityReplicationRead:
        return await self.replication_service.replicate(
            target_server_ids=payload.target_server_ids,
            operation_type="identity:permissions:apply",
            command=self._permission_command(payload),
        )

    async def replicate(self, template_id: UUID, payload: PermissionReplicateRequest) -> IdentityReplicationRead:
        template = await self.repository.get_by_id(template_id)
        if template is None:
            raise IdentityNotFoundError("Permission template not found")
        return await self.replication_service.replicate(
            target_server_ids=payload.target_server_ids,
            operation_type=f"identity:permissions:{template.id}:replicate",
            command=self._permission_command(template),
        )

    @staticmethod
    def _permission_command(template: PermissionTemplate | PermissionApplyRequest) -> str:
        recursive = " -R" if template.recursive else ""
        commands = []
        if template.owner or template.group:
            owner_group = f"{template.owner or ''}:{template.group or ''}"
            commands.append(f"sudo chown{recursive} {quote(owner_group)} {quote(template.path)}")
        if template.mode:
            commands.append(f"sudo chmod{recursive} {quote(template.mode)} {quote(template.path)}")
        if not commands:
            raise IdentityValidationError("No permission operation requested")
        return " && ".join(commands)
    PermissionPresetRead,
