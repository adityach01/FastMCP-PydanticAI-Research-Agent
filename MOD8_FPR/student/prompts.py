SYSTEM_PROMPT = """
You are a rigorous research analyst.
Use only the provided source snippets and cite URLs in your output.
If evidence is weak, explicitly list limitations.
Return concise, structured analysis.
""".strip()


def build_user_prompt(topic: str, sources: list[dict]) -> str:
    rendered_sources = []
    for i, s in enumerate(sources[:20], start=1):
        rendered_sources.append(
            f"[{i}] {s.get('title', 'Untitled')}\nURL: {s.get('url', '')}\nSnippet: {s.get('snippet', '')}"
        )

    return (
        f"Topic: {topic}\n\n"
        "Build an executive briefing with key findings and limitations from the sources below."
        "\n\nSources:\n"
        + "\n\n".join(rendered_sources)
    )
