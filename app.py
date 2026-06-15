"""
app.py — UCI CS Professor RAG: Web Interface

Gradio-based interface for querying professor reviews.
- Left: question input
- Right: answer + sources
- Enforces grounding through system prompt
"""

import gradio as gr
from generate import ask


def handle_query(question: str) -> tuple[str, str]:
    """
    Handle a user query and return answer + sources.

    Args:
        question: User's question

    Returns:
        (answer_text, sources_markdown)
    """
    if not question.strip():
        return "Please enter a question.", ""

    result = ask(question.strip())
    answer = result["answer"]
    sources_markdown = "\n".join(
        f"• [{name}]({url})" for name, url in result["sources"]
    ) if result["sources"] else "(No sources retrieved)"

    return answer, sources_markdown


def build_ui():
    """Build the Gradio UI."""
    with gr.Blocks(title="UCI CS Professor Reviews RAG") as demo:
        gr.Markdown("""
        # UCI CS Professor Reviews Search

        Ask questions about UCI Computer Science professors based on real student reviews.

        **Examples:**
        - "What do students say about Professor Thornton's grading fairness?"
        - "Who do students recommend for ICS 46 - Shindler or Klefstad?"
        - "What are common complaints about CS professors at UCI?"
        """)

        with gr.Row():
            with gr.Column(scale=1):
                question = gr.Textbox(
                    label="Your Question",
                    placeholder="Ask about a professor, course, difficulty, grading, etc.",
                    lines=3,
                )
                search_btn = gr.Button("Search", variant="primary", size="lg")

            with gr.Column(scale=1):
                answer_box = gr.Textbox(
                    label="Answer (from student reviews)",
                    lines=8,
                    interactive=False,
                )
                gr.Markdown("#### Sources")
                sources_box = gr.Markdown()

        # Wire up click and submit
        search_btn.click(
            handle_query,
            inputs=question,
            outputs=[answer_box, sources_box],
        )
        question.submit(
            handle_query,
            inputs=question,
            outputs=[answer_box, sources_box],
        )

        gr.Markdown("""
        ---
        **How it works:** This system retrieves student reviews and uses an LLM to synthesize
        answers grounded in those reviews. Answers cite their sources — if the reviews don't
        contain enough information, the system will say so.
        """)

    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)
