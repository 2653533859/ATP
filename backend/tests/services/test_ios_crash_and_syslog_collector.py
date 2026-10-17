"""iOS 崩溃堆栈捕获与 Syslog 归档服务单测 (T4.1)"""

from __future__ import annotations

import pytest

from app.services.ios_crash_and_syslog_collector import (
    clear_crash_and_syslog_store,
    get_crash_report,
    get_recent_syslog,
    ingest_syslog_lines,
    list_crash_reports,
    parse_and_record_crash,
)

SAMPLE_IPS_CRASH = """
Incident Identifier: 12345678-ABCD-EF01-2345-6789ABCDEF01
CrashReporter Key:   abcdef123456
Process:             DemoApp [1042]
Path:                /private/var/containers/Bundle/Application/DemoApp.app/DemoApp
Identifier:          com.example.demoapp
Version:             1.2.0 (42)
Code Type:           ARM-64 (Native)
Role:                Foreground
Parent Process:      launchd [1]

Date/Time:           2026-10-17 12:00:00.000 +0800
OS Version:          iPhone OS 17.4.1 (21E236)
Report Version:      104

Exception Type:  EXC_BAD_ACCESS (SIGSEGV)
Exception Subtype: KERN_INVALID_ADDRESS at 0x0000000000000010
Termination Reason: SIGNAL 11 Segmentation fault: 11
Terminating Process: exc handler [1042]
Triggered by Thread: 0

Thread 0 Crashed:
0   DemoApp                       	0x0000000104824310 -[PaymentViewController submitOrder:] + 128
1   UIKitCore                     	0x000000018590c240 -[UIApplication sendAction:to:from:forEvent:] + 96
2   UIKitCore                     	0x00000001853d21b4 -[UIControl sendAction:to:forEvent:] + 112
3   libsystem_pthread.dylib       	0x00000001da8992c0 start_wqthread + 8
"""


@pytest.fixture(autouse=True)
def clean_state():
    clear_crash_and_syslog_store()
    yield
    clear_crash_and_syslog_store()


def test_syslog_ingestion_and_buffering():
    udid = "00008101-SYSLOG-01"

    lines = [
        "[12:00:01] SpringBoard[52] <Notice>: Screen unlocked",
        "[12:00:02] DemoApp[1042] <Notice>: Loading cart view",
        "[12:00:03] DemoApp[1042] <Error>: Failed to connect database cache",
        "[12:00:04] DemoApp[1042] <Fault>: Fatal memory access violation",
    ]

    count = ingest_syslog_lines(udid, lines)
    assert count == 4

    recent = get_recent_syslog(udid, limit=10)
    assert len(recent) == 4
    assert recent[2]["level"] == "error"
    assert recent[3]["level"] == "fault"


def test_parse_and_record_crash_report():
    udid = "00008101-CRASH-01"
    run_id = "run_ios_e2e_404"
    step_idx = 3

    record = parse_and_record_crash(
        udid=udid,
        raw_crash_text=SAMPLE_IPS_CRASH,
        run_id=run_id,
        step_index=step_idx,
    )

    assert record.udid == udid
    assert record.process_name == "DemoApp"
    assert record.bundle_id == "com.example.demoapp"
    assert "EXC_BAD_ACCESS" in record.exception_type
    assert "Segmentation fault" in record.termination_reason
    assert record.crashed_thread == 0
    assert len(record.stack_trace) == 4
    assert "PaymentViewController" in record.stack_trace[0]
    assert len(record.crash_fingerprint) == 16
    assert record.run_id == run_id
    assert record.step_index == 3

    # 查验证书与列表
    fetched = get_crash_report(record.crash_id)
    assert fetched is not None
    assert fetched.crash_fingerprint == record.crash_fingerprint

    by_run = list_crash_reports(run_id=run_id)
    assert len(by_run) == 1
    assert by_run[0]["crash_id"] == record.crash_id
