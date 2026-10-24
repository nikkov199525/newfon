"""Exercise source chunking without importing NVDA modules."""
import ast
from pathlib import Path
import unittest

DRIVER = Path(__file__).resolve().parents[1] / "src/synthDrivers/newfon/__init__.py"
tree = ast.parse(DRIVER.read_text(encoding="utf-8-sig"))
names = {"MIN_FIRST_SOURCE_SEGMENT_CHARS", "FIRST_SOURCE_SEGMENT_CHARS",
         "MIN_SOURCE_SEGMENT_CHARS", "MAX_SOURCE_SEGMENT_CHARS"}
selected = [node for node in tree.body if
            isinstance(node, ast.FunctionDef) and node.name == "_sourceSegments" or
            isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets)]
namespace = {}
exec(compile(ast.Module(body=selected, type_ignores=[]), str(DRIVER), "exec"), namespace)
segments = namespace["_sourceSegments"]


class SourceSegments(unittest.TestCase):
    def test_preserves_cardinal_at_every_first_boundary(self):
        number = "1" + "0" * 150
        for prefix_size in range(161):
            text = "а" * prefix_size + number + " конец"
            with self.subTest(prefix_size=prefix_size):
                chunks = list(segments(text))
                self.assertEqual("".join(chunks), text)
                self.assertEqual(sum(number in chunk for chunk in chunks), 1)

    def test_zero_run_and_later_boundary(self):
        for text in ["0" * 10000, "начало " + "0" * 1000 + " конец",
                     "вводное. " + "а" * 680 + "9" * 153 + " конец"]:
            chunks = list(segments(text))
            self.assertEqual("".join(chunks), text)
            for left, right in zip(chunks, chunks[1:]):
                self.assertFalse(left[-1].isdigit() and right[0].isdigit())

    def test_ordinary_text_still_has_bounded_chunks(self):
        text = "обычный текст. " * 200
        chunks = list(segments(text))
        self.assertEqual("".join(chunks), text)
        self.assertLessEqual(len(chunks[0]), 161)
        self.assertTrue(all(len(chunk) <= 701 for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
