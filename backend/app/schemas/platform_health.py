"""Bounded host-agent reports. Unknown fields and non-finite readings are rejected."""
from datetime import datetime, timezone, timedelta
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator

Percent = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
Count = Annotated[int, Field(ge=0, le=2**63-1)]
Rate = Annotated[float, Field(ge=0, le=1e18, allow_inf_nan=False)]
Sha = Annotated[str, Field(pattern=r'^[0-9a-f]{40}$')]
Name = Annotated[str, Field(min_length=1, max_length=160, pattern=r'^[^\x00-\x1f\x7f]+$')]


class Bounded(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class HostIdentity(Bounded):
    hostname: Name
    distribution: Name
    version: Name
    kernel: Name
    architecture: Name
    cpu_model: Name
    cpu_cores: int = Field(ge=1, le=65536)
    uptime_seconds: Rate


class Filesystem(Bounded):
    mount: Name
    total_bytes: Count
    available_bytes: Count
    used_percent: Percent
    inode_used_percent: Percent | None = None


class Interface(Bounded):
    name: Name
    state: Literal['up', 'down', 'unknown']
    rx_bytes_per_second: Rate | None = None
    tx_bytes_per_second: Rate | None = None
    rx_errors: Count = 0
    tx_errors: Count = 0


class DiskIO(Bounded):
    device: Name
    read_bytes_per_second: Rate | None = None
    write_bytes_per_second: Rate | None = None


class Metrics(Bounded):
    cpu_percent: Percent | None = None
    load: list[Rate] = Field(default_factory=list, max_length=3)
    memory_total_bytes: Count
    memory_available_bytes: Count
    memory_used_percent: Percent
    swap_total_bytes: Count = 0
    swap_used_bytes: Count = 0
    filesystems: list[Filesystem] = Field(default_factory=list, max_length=32)
    interfaces: list[Interface] = Field(default_factory=list, max_length=64)
    disk_io: list[DiskIO] = Field(default_factory=list, max_length=64)


class Container(Bounded):
    name: Name
    status: Literal['running', 'exited', 'created', 'restarting', 'paused', 'dead', 'removing', 'unknown']
    health: Literal['healthy', 'unhealthy', 'starting'] | None = None
    restarts: Count = 0
    cpu_percent: Rate | None = None  # Docker may exceed 100% across multiple cores.
    memory_used_bytes: Count | None = None
    memory_limit_bytes: Count | None = None
    revision: Sha | None = None


class DockerEngine(Bounded):
    available: bool
    context: Name
    name: Name | None = None
    operating_system: Name | None = None
    cpus: int | None = Field(default=None, ge=1, le=65536)
    memory_bytes: Count | None = None


class Deployment(Bounded):
    process_active: bool | None = None
    attempt_id: UUID | None = None
    target_sha: Sha | None = None
    deployed_sha: Sha | None = None
    stage: Literal['unknown', 'checking', 'idle', 'waiting_for_release', 'waiting_for_build', 'downloading',
                   'verifying', 'loading_images', 'backing_up', 'migrating', 'starting', 'health_check',
                   'rollback', 'complete', 'failed'] = 'unknown'
    result: Literal['unknown', 'running', 'waiting', 'idle', 'success', 'failed'] = 'unknown'
    rollback: Literal['not_needed', 'attempted', 'succeeded', 'failed'] = 'not_needed'
    started_at: AwareDatetime | None = None
    updated_at: AwareDatetime | None = None
    deployed_at: AwareDatetime | None = None
    last_check_at: AwareDatetime | None = None
    error_type: Annotated[str, Field(max_length=100, pattern=r'^[A-Za-z0-9_.-]*$')] | None = None


class Github(Bounded):
    checked_at: AwareDatetime | None = None
    main_sha: Sha | None = None
    release_sha: Sha | None = None
    build_sha: Sha | None = None
    build_status: Literal['unknown', 'queued', 'in_progress', 'completed'] = 'unknown'
    build_result: Literal['success', 'failure', 'cancelled', 'skipped', 'timed_out', 'action_required', 'neutral', 'stale', 'startup_failure'] | None = None
    build_run_id: int | None = Field(default=None, ge=1)
    error: Literal['unavailable', 'rate_limited'] | None = None


class AgentReport(Bounded):
    schema_version: Literal[1] = 1
    sample_id: UUID
    host_id: str = Field(pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$')
    observed_at: AwareDatetime
    host: HostIdentity
    metrics: Metrics
    docker: DockerEngine
    containers: list[Container] = Field(default_factory=list, max_length=128)
    application_ready: bool | None = None
    deployment: Deployment = Field(default_factory=Deployment)
    deployments: list[Deployment] = Field(default_factory=list, max_length=30)
    github: Github = Field(default_factory=Github)
    collection_errors: list[Literal['docker_unavailable', 'docker_stats_unavailable', 'filesystem_unavailable',
                                  'deployment_unavailable', 'github_unavailable', 'github_reporting_unavailable', 'application_unavailable']] = Field(default_factory=list, max_length=7)

    @model_validator(mode='after')
    def valid_sample(self):
        now = datetime.now(timezone.utc)
        if not now - timedelta(hours=24) <= self.observed_at <= now + timedelta(seconds=60):
            raise ValueError('Sample must be within the last 24 hours and at most 60 seconds ahead')
        if self.metrics.memory_available_bytes > self.metrics.memory_total_bytes or self.metrics.swap_used_bytes > self.metrics.swap_total_bytes:
            raise ValueError('Invalid memory counters')
        if any(row.available_bytes > row.total_bytes for row in self.metrics.filesystems):
            raise ValueError('Invalid filesystem counters')
        if len({row.name for row in self.containers}) != len(self.containers):
            raise ValueError('Duplicate container names')
        return self
