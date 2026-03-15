from typing import List, Optional

def build_extraction_prompt(
    brand_name: str,
    competitor_names: List[str],
    platform: str,
    query_intent: str,
    query_text: str,
    response_text: str,
) -> str:
    """
    Builds the prompt for the LLM to extract competitor and brand mentions.
    """
    competitors_str = ", ".join(competitor_names) if competitor_names else "None specified."
    return (
        f"Analyze the following AI search response and extract any mentions "
        f"of the brand to analyze or its known competitors. "
        f"Identify the sentiment, position in the response, and whether it's "
        f"a first recommendation (if applicable and clear from context). "
        f"Focus only on comparative or explicit recommendation language. "
        f"If a competitor is mentioned, determine its position (1-indexed based on first appearance) "
        f"and the snippet of text that led to its identification."
        f"If the brand is mentioned, determine its position and related sentiment/snippet."
        f"If no brand or competitor is mentioned in a comparative or recommendation context, "
        f"return empty lists for competitors_found and mentioned=false for brand_mention."
        f"The output MUST be a JSON object conforming to the LLMExtractionResult schema."
        f"Ensure all fields are correctly populated based on the response content."
        f"Do not include any other text or explanation outside the JSON."
        f"\n\n"
        f"AI Platform: {platform}\n"
        f"Query Intent: {query_intent}\n"
        f'Original Query: "{query_text}"\n'
        f'Brand to Analyze: "{brand_name}"\n'
        f"Known Competitors: {competitors_str}\n\n"
        f"Response Text:\n{response_text}\n\n"
        f"Provide the output in the specified JSON format."
    )
