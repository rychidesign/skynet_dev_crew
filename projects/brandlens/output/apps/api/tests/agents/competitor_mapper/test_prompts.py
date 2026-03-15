from apps.api.agents.competitor_mapper_prompts import build_analysis_prompt, SYSTEM_PROMPT

def test_build_analysis_prompt():
    response_text = "This is a response mentioning CompetitorA and CompetitorB."
    competitors = ["CompetitorA", "CompetitorB"]
    platform = "ChatGPT"
    query_text = "Compare BrandX with its competitors."
    prompt = build_analysis_prompt(response_text, competitors, platform, query_text)
    assert "CompetitorA, CompetitorB" in prompt
    assert "ChatGPT" in prompt
    assert "This is a response" in prompt
    assert "position_rank" in prompt
    assert SYSTEM_PROMPT.strip() == """You are a competitive analysis extraction system. You analyze AI-generated responses and identify mentions of competitor brands. You MUST respond with valid JSON only. No explanation, no markdown, no prose."""
