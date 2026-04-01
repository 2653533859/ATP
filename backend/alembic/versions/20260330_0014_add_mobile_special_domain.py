"""add mobile special domain

Revision ID: 20260330_0014
Revises: 20260328_0013
Create Date: 2026-03-30

This migration creates the mobile special testing domain tables:
- mobile_special_tasks: Android专项任务定义
- mobile_special_runs: 专项任务执行记录
- mobile_metric_samples: 时序采样点
- mobile_incidents: Crash/ANR/fatal log/watchdog事件
- mobile_run_artifacts: CSV/JSON/截图/原始日志/trace附件
- global_variables: 项目级或平台级共享变量库
"""
from alembic import op
import sqlalchemy as sa


revision = '20260330_0014'
down_revision = '20260328_0013'
branch_labels = None
depends_on = None


# Enums
task_type_enum = sa.Enum('performance', 'stability', 'fluency', name='task_type')
source_type_enum = sa.Enum('apk_only', 'case', 'suite', 'monkey', name='source_type')
device_scope_type_enum = sa.Enum('single_device', 'device_group', 'manual_pick', name='device_scope_type')
run_status_enum = sa.Enum('pending', 'running', 'completed', 'failed', 'stopped', name='run_status')
trigger_type_enum = sa.Enum('manual', 'schedule', 'webhook', name='trigger_type')
incident_type_enum = sa.Enum('crash', 'anr', 'fatal_log', 'watchdog', name='incident_type')
metric_type_enum = sa.Enum(
    'cpu_pct', 'mem_mb', 'fps', 'jank_count', 'frame_time_ms',
    'battery_pct', 'temperature_c', 'network_rx_kb', 'network_tx_kb',
    name='metric_type'
)
artifact_type_enum = sa.Enum('csv', 'json', 'screenshot', 'raw_log', 'trace', name='artifact_type')
scope_type_enum = sa.Enum('global', 'project', name='scope_type')


def upgrade() -> None:
    # Create enums
    task_type_enum.create(op.get_bind(), checkfirst=True)
    source_type_enum.create(op.get_bind(), checkfirst=True)
    device_scope_type_enum.create(op.get_bind(), checkfirst=True)
    run_status_enum.create(op.get_bind(), checkfirst=True)
    trigger_type_enum.create(op.get_bind(), checkfirst=True)
    incident_type_enum.create(op.get_bind(), checkfirst=True)
    metric_type_enum.create(op.get_bind(), checkfirst=True)
    artifact_type_enum.create(op.get_bind(), checkfirst=True)
    scope_type_enum.create(op.get_bind(), checkfirst=True)

    # mobile_special_tasks table
    op.create_table(
        'mobile_special_tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=256), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('task_type', sa.Enum('performance', 'stability', 'fluency', name='task_type'), nullable=False),
        sa.Column('source_type', sa.Enum('apk_only', 'case', 'suite', 'monkey', name='source_type'), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('device_scope_type', sa.Enum('single_device', 'device_group', 'manual_pick', name='device_scope_type'), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=True),
        sa.Column('device_group_tag', sa.String(length=128), nullable=True),
        sa.Column('apk_id', sa.Integer(), nullable=True),
        sa.Column('app_package', sa.String(length=256), nullable=True),
        sa.Column('config_json', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('schedule_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('cron_expression', sa.String(length=64), nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['apk_id'], ['apks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_mobile_special_tasks_project_id', 'mobile_special_tasks', ['project_id'])
    op.create_index('ix_mobile_special_tasks_task_type', 'mobile_special_tasks', ['task_type'])
    op.create_index('ix_mobile_special_tasks_device_id', 'mobile_special_tasks', ['device_id'])

    # mobile_special_runs table
    op.create_table(
        'mobile_special_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('task_type', sa.Enum('performance', 'stability', 'fluency', name='task_type'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'running', 'completed', 'failed', 'stopped', name='run_status'), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=True),
        sa.Column('device_serial', sa.String(length=128), nullable=True),
        sa.Column('apk_id', sa.Integer(), nullable=True),
        sa.Column('app_package', sa.String(length=256), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.BigInteger(), nullable=True),
        sa.Column('summary_json', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('config_snapshot', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('trigger_type', sa.Enum('manual', 'schedule', 'webhook', name='trigger_type'), nullable=False),
        sa.Column('triggered_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['mobile_special_tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['apk_id'], ['apks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['triggered_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_mobile_special_runs_task_id', 'mobile_special_runs', ['task_id'])
    op.create_index('ix_mobile_special_runs_status', 'mobile_special_runs', ['status'])
    op.create_index('ix_mobile_special_runs_started_at', 'mobile_special_runs', ['started_at'])

    # mobile_metric_samples table
    op.create_table(
        'mobile_metric_samples',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('sample_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metric_type', sa.Enum('cpu_pct', 'mem_mb', 'fps', 'jank_count', 'frame_time_ms', 'battery_pct', 'temperature_c', 'network_rx_kb', 'network_tx_kb', name='metric_type'), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('source', sa.String(length=128), nullable=True),
        sa.Column('extra_json', sa.JSON(), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['run_id'], ['mobile_special_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_mobile_metric_samples_run_id', 'mobile_metric_samples', ['run_id'])
    op.create_index('ix_mobile_metric_samples_sample_time', 'mobile_metric_samples', ['sample_time'])
    op.create_index('ix_mobile_metric_samples_metric_type', 'mobile_metric_samples', ['metric_type'])

    # mobile_incidents table
    op.create_table(
        'mobile_incidents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('incident_type', sa.Enum('crash', 'anr', 'fatal_log', 'watchdog', name='incident_type'), nullable=False),
        sa.Column('event_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('title', sa.String(length=512), nullable=True),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('process_name', sa.String(length=256), nullable=True),
        sa.Column('thread_name', sa.String(length=256), nullable=True),
        sa.Column('artifact_path', sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['mobile_special_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_mobile_incidents_run_id', 'mobile_incidents', ['run_id'])
    op.create_index('ix_mobile_incidents_event_time', 'mobile_incidents', ['event_time'])
    op.create_index('ix_mobile_incidents_incident_type', 'mobile_incidents', ['incident_type'])

    # mobile_run_artifacts table
    op.create_table(
        'mobile_run_artifacts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('artifact_type', sa.Enum('csv', 'json', 'screenshot', 'raw_log', 'trace', name='artifact_type'), nullable=False),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('file_name', sa.String(length=256), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['mobile_special_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_mobile_run_artifacts_run_id', 'mobile_run_artifacts', ['run_id'])

    # global_variables table
    op.create_table(
        'global_variables',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('scope_type', sa.Enum('global', 'project', name='scope_type'), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('key', sa.String(length=256), nullable=False),
        sa.Column('value_encrypted', sa.Text(), nullable=False),
        sa.Column('is_secret', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_global_variables_scope_type', 'global_variables', ['scope_type'])
    op.create_index('ix_global_variables_project_id', 'global_variables', ['project_id'])
    op.create_index('ix_global_variables_key', 'global_variables', ['key'])


def downgrade() -> None:
    op.drop_table('global_variables')
    op.drop_table('mobile_run_artifacts')
    op.drop_table('mobile_incidents')
    op.drop_table('mobile_metric_samples')
    op.drop_table('mobile_special_runs')
    op.drop_table('mobile_special_tasks')

    scope_type_enum.drop(op.get_bind(), checkfirst=True)
    artifact_type_enum.drop(op.get_bind(), checkfirst=True)
    metric_type_enum.drop(op.get_bind(), checkfirst=True)
    incident_type_enum.drop(op.get_bind(), checkfirst=True)
    trigger_type_enum.drop(op.get_bind(), checkfirst=True)
    run_status_enum.drop(op.get_bind(), checkfirst=True)
    device_scope_type_enum.drop(op.get_bind(), checkfirst=True)
    source_type_enum.drop(op.get_bind(), checkfirst=True)
    task_type_enum.drop(op.get_bind(), checkfirst=True)
