"""Simple unit tests for schemas and tools."""
import pytest
from app.schemas.blocks import TextBlock, KPICard, TableBlock, ChartBlock, ReportBlock
from app.schemas.tasks import TaskSpec, CriticVerdict, DepartmentEnum


def test_text_block_serialization():
    block = TextBlock(block_id="1", title="Test", content="Hello world", order=0)
    data = block.model_dump()
    assert data["block_type"] == "text"
    assert data["content"] == "Hello world"


def test_kpi_card():
    card = KPICard(block_id="2", title="Revenue", metric_name="Revenue", value=1234.56, unit="RUB", order=1)
    assert card.value == 1234.56
    assert card.verification_status == "verified"


def test_table_block():
    from app.schemas.blocks import TableColumn
    block = TableBlock(
        block_id="3", title="Sales", order=2,
        columns=[TableColumn(key="period", label="Период", dtype="string"),
                 TableColumn(key="value", label="Значение", dtype="number")],
        rows=[{"period": "Q1", "value": 100}, {"period": "Q2", "value": 200}],
    )
    assert len(block.rows) == 2


def test_task_spec():
    task = TaskSpec(session_id="sess1", department=DepartmentEnum.DATA_EXTRACTION, description="Extract data")
    assert task.department == DepartmentEnum.DATA_EXTRACTION
    assert task.max_retries == 2


def test_critic_verdict():
    verdict = CriticVerdict(task_id="t1", status="APPROVED", score=0.9)
    assert verdict.status == "APPROVED"


def test_fingerprint_build_and_verify():
    from app.document_pipeline.fingerprint import NumericFingerprint
    fp = NumericFingerprint()
    chunks = [{"chunk_id": "c1", "content": "Выручка составила 1234.56 млн руб в Q1 2023", "page_number": 1}]
    fp.build(chunks)
    assert len(fp.catalog) > 0

    result = fp.verify(1234.56, "выручка")
    assert result.status in ("VERIFIED", "NOT_FOUND")


def test_text_chunker():
    from app.document_pipeline.chunker import TextChunker
    chunker = TextChunker(chunk_size=50, overlap=10)
    text = "Это первое предложение. Это второе предложение. Это третье предложение. И четвёртое тоже."
    chunks = chunker.chunk(text)
    assert len(chunks) >= 1
    for c in chunks:
        assert c.content


def test_statistics_tool():
    from app.tools.math_engine.tools import calculate_statistics
    result = calculate_statistics([1.0, 2.0, 3.0, 4.0, 5.0], ["mean", "std", "min", "max"])
    assert result["mean"] == 3.0
    assert result["min"] == 1.0
    assert result["max"] == 5.0


def test_growth_rate_tool():
    from app.tools.math_engine.tools import calculate_growth_rate
    result = calculate_growth_rate([100.0, 110.0, 121.0], ["2021", "2022", "2023"])
    assert "cagr_pct" in result
    assert abs(result["cagr_pct"] - 10.0) < 0.1


def test_correlation_tool():
    from app.tools.math_engine.tools import calculate_correlation
    result = calculate_correlation([1.0, 2.0, 3.0, 4.0, 5.0], [2.0, 4.0, 6.0, 8.0, 10.0])
    assert result["correlation"] == pytest.approx(1.0, abs=0.01)
    assert result["significant"] is True


def test_sentiment_tool():
    from app.tools.nlp_tools.tools import analyze_sentiment
    result = analyze_sentiment(["This is great!", "This is terrible and awful."])
    assert "results" in result
    assert len(result["results"]) == 2
