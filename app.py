"""
app.py — UCI CS Professor RAG: Web Interface
"""

import gradio as gr
from generate import ask


def handle_query(question: str) -> tuple[str, str]:
    if not question.strip():
        return "Please enter a question.", ""

    result = ask(question.strip())
    answer = result["answer"]

    if result["sources"]:
        items = "".join(
            f'<li><a href="{url}" target="_blank" rel="noopener noreferrer">{name}</a></li>'
            for name, url in result["sources"]
        )
        sources_html = f"<ul>{items}</ul>"
    else:
        sources_html = "<p><em>No sources retrieved.</em></p>"

    return answer, sources_html


def build_ui():
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
                sources_box = gr.HTML()          # ← HTML renders <a> tags correctly

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