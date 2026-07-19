"""Regression checks for the dedicated report-chat workspace."""

from pathlib import Path
import re
import unittest

from tools.report_normalization import normalize_final_report


ROOT = Path(__file__).resolve().parents[1]


class ReportChatUiTests(unittest.TestCase):
    def test_internal_rag_context_is_not_a_fillable_gap(self):
        report = normalize_final_report({
            "missing_information": [
                "Current medication list and doses.",
                "RAG context for citations 'guide.pdf, p. 203' [5] and 'guide.pdf, p. 40' [6].",
            ],
        })

        self.assertEqual(
            report["missing_information"],
            ["Current medication list and doses."],
        )

    def test_fill_workspace_is_outside_the_fixed_composer(self):
        html = (ROOT / "frontend" / "report_chat.html").read_text(encoding="utf-8")
        fill_start = html.index('data-report-fill-panel')
        messages_start = html.index('data-report-chat-messages')
        composer_start = html.index('class="report-chat-bottom')

        self.assertLess(fill_start, messages_start)
        self.assertLess(messages_start, composer_start)

    def test_missing_information_list_has_its_own_scroll_area(self):
        css = (ROOT / "frontend" / "report_chat.css").read_text(encoding="utf-8")
        body_rule = re.search(
            r"\.report-fill-panel__body\s*\{(?P<body>.*?)\}",
            css,
            flags=re.DOTALL,
        )

        self.assertIsNotNone(body_rule)
        declarations = body_rule.group("body")
        self.assertIn("min-height: 0", declarations)
        self.assertIn("overflow-y: auto", declarations)
        self.assertIn("scrollbar-gutter: stable", declarations)

    def test_fill_mode_swaps_chat_and_composer_out_of_view(self):
        javascript = (ROOT / "frontend" / "submissions.js").read_text(encoding="utf-8")

        self.assertIn("messages.hidden = isActive", javascript)
        self.assertIn("bottom.hidden = isActive", javascript)
        self.assertIn('event.key !== "Escape"', javascript)

    def test_generated_report_editor_is_not_rendered(self):
        html = (ROOT / "frontend" / "submissions.html").read_text(encoding="utf-8")
        javascript = (ROOT / "frontend" / "submissions.js").read_text(encoding="utf-8")

        self.assertNotIn("Edit generated report", html)
        self.assertNotIn("data-report-editor", html)
        self.assertNotIn("data-report-edit-toggle", javascript)
        self.assertNotIn('fetch("report-chat/report-edit"', javascript)


if __name__ == "__main__":
    unittest.main()
