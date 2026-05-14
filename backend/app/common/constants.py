"""
Centralized constant definitions for NexusOps.

These enums and constants are shared across backend modules and exposed to the frontend API.
"""

from enum import StrEnum


class ServerStatus(StrEnum):
    """Current operational status of a server."""

    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class ServerEnvironment(StrEnum):
    """Environment classification for a server."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"
    LAB = "lab"


class ServerSshAuthMethod(StrEnum):
    """SSH authentication method."""

    KEY = "key"
    PASSWORD = "password"


class InventoryLifecycleState(StrEnum):
    """Inventory entry lifecycle state.

    States represent the journey of infrastructure from discovery to archive:
    - DISCOVERED: Found via infrastructure provider, not yet added to inventory
    - UNMANAGED: In inventory but not actively managed
    - MANAGED: In inventory and actively managed
    - PROVISIONED: Created by NexusOps provisioning
    - ARCHIVED: Marked for historical retention, not active
    """

    DISCOVERED = "discovered"
    UNMANAGED = "unmanaged"
    MANAGED = "managed"
    PROVISIONED = "provisioned"
    ARCHIVED = "archived"


class InventorySyncStatus(StrEnum):
    """Synchronization status between inventory and infrastructure provider.

    Tracks reconciliation state between Inventory CMDB and live infrastructure:
    - UNKNOWN: Synchronization state not yet determined
    - SYNCED: Inventory entry matches infrastructure provider state
    - UNMANAGED: Infrastructure exists, not yet added to inventory
    - ORPHANED: Inventory entry no longer exists in infrastructure provider
    - MISMATCH: Inventory and provider metadata disagree
    - ARCHIVED: Marked as archived in inventory
    """

    UNKNOWN = "unknown"
    SYNCED = "synced"
    UNMANAGED = "unmanaged"
    ORPHANED = "orphaned"
    MISMATCH = "mismatch"
    ARCHIVED = "archived"


class InventoryHealthStatus(StrEnum):
    """Lightweight host reachability state for inventory execution targets."""

    ONLINE = "online"
    UNREACHABLE = "unreachable"
    UNKNOWN = "unknown"
    PROVISIONING = "provisioning"
    ARCHIVED = "archived"
    SYNC_ERROR = "sync_error"


# Default values for new inventory entries
INVENTORY_DEFAULTS = {
    "status": ServerStatus.UNKNOWN,
    "lifecycle_state": InventoryLifecycleState.MANAGED,
    "sync_status": InventorySyncStatus.UNKNOWN,
    "environment": ServerEnvironment.LAB,
    "ssh_port": 22,
    "ssh_auth_method": ServerSshAuthMethod.KEY,
    "managed": True,
    "source": "manual",
}

# Display labels for states
STATE_LABELS = {
    ServerStatus.UNKNOWN: "Unknown",
    ServerStatus.ONLINE: "Online",
    ServerStatus.OFFLINE: "Offline",
    ServerStatus.MAINTENANCE: "Maintenance",
    InventoryLifecycleState.DISCOVERED: "Discovered",
    InventoryLifecycleState.UNMANAGED: "Unmanaged",
    InventoryLifecycleState.MANAGED: "Managed",
    InventoryLifecycleState.PROVISIONED: "Provisioned",
    InventoryLifecycleState.ARCHIVED: "Archived",
    InventorySyncStatus.UNKNOWN: "Unknown",
    InventorySyncStatus.SYNCED: "Synced",
    InventorySyncStatus.UNMANAGED: "Unmanaged",
    InventorySyncStatus.ORPHANED: "Orphaned",
    InventorySyncStatus.MISMATCH: "Mismatch",
    InventorySyncStatus.ARCHIVED: "Archived",
    InventoryHealthStatus.ONLINE: "Online",
    InventoryHealthStatus.UNREACHABLE: "Unreachable",
    InventoryHealthStatus.UNKNOWN: "Unknown",
    InventoryHealthStatus.PROVISIONING: "Provisioning",
    InventoryHealthStatus.ARCHIVED: "Archived",
    InventoryHealthStatus.SYNC_ERROR: "Sync Error",
}
