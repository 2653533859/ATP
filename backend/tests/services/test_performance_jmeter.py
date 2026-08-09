from pathlib import Path

from app.services.performance_jmeter import parse_jmeter_jtl


def test_parse_jmeter_jtl_returns_common_summary_and_thresholds(tmp_path: Path):
    path = tmp_path / "result.jtl"
    path.write_text(
        "timeStamp,elapsed,label,responseCode,success,bytes,sentBytes\n"
        "1000,100,health,200,true,120,20\n"
        "2000,300,health,500,false,80,25\n"
        "3000,200,health,200,true,100,22\n",
        encoding="utf-8",
    )

    result = parse_jmeter_jtl(path, {"error_rate": ["<= 0.5"]})

    assert result["executor"] == "jmeter"
    assert result["iterations"] == 3
    assert result["error_rate"] == 1 / 3
    assert result["rps"] == 1.5
    assert result["data_received"] == 300
    assert result["thresholds"]["error_rate"]["<= 0.5"]["ok"] is True
