from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


PipelineStatus = Literal["queued", "running", "succeeded", "failed"]
PipelineStage = Literal[
    "preparing_inputs",
    "running_pipeline",
    "running_final",
    "running_format",
    "running_transformer",
    "running_ingestor",
    "completed",
    "failed",
    "matching_complete",
    "final_complete",
    "format_complete",
]


class PipelineArtifacts(BaseModel):
    input_offer_path: str | None = None
    input_cv_dir: str | None = None
    tests_file_path: str | None = None
    matching_results_dir: str | None = None
    final_results_dir: str | None = None
    formatted_cv_dir: str | None = None
    archive_dir: str | None = None
    transformed_json_path: str | None = None
    reuse_session_id: str | None = None
    detected_profile: str | None = None
    detected_seniority: str | None = None
    sftp_retry_count: int = 0


class PipelineJob(BaseModel):
    job_id: str
    session_id: str
    status: PipelineStatus = "queued"
    stage: PipelineStage = "preparing_inputs"
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    matching_completed_at: datetime | None = None
    final_completed_at: datetime | None = None
    format_completed_at: datetime | None = None
    input_mode: str = "cv_folder_offer"
    offer_filename: str | None = None
    cv_count: int = 0
    archive_enabled: bool = True
    format_cvs: bool = False
    template_name: str | None = None
    limit_count: int | None = None
    pipeline_exit_code: int | None = None
    transform_exit_code: int | None = None
    ingest_exit_code: int | None = None
    error_message: str | None = None
    # New fields backed by the PostgreSQL jobs.pipeline_jobs table (migration 003)
    offer_id: str | None = None
    created_by: str | None = None
    updated_at: datetime | None = None
    artifacts: PipelineArtifacts = Field(default_factory=PipelineArtifacts)


class JobCreateResponse(BaseModel):
    job_id: str
    session_id: str
    status: PipelineStatus


class JobStatusResponse(BaseModel):
    job: PipelineJob
    artifacts: dict[str, Any] | None = None
    progress: dict[str, int] = Field(default_factory=dict)
