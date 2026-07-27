from app.rag import build_index, search


def test_policy_search_returns_citable_pto_evidence():
    build_index()
    result = search("How much notice is needed for PTO?", 3)
    assert result
    assert any(item["document"] == "pto_policy.md" for item in result)
    assert all({"id", "section", "text"} <= item.keys() for item in result)
