import unittest

from hsr_version_inspector.diff import CharacterChange, tokenize_text_diff
from hsr_version_inspector.diff.models import CharacterChange as ModelCharacterChange
from hsr_version_inspector.diff.tokenize import (
    tokenize_text_diff as model_tokenize_text_diff,
)
from hsr_version_inspector.download import DownloadTarget
from hsr_version_inspector.download.models import DownloadTarget as ModelDownloadTarget
from hsr_version_inspector.pdf import PdfRenderer
from hsr_version_inspector.pdf.diff import PdfDiffMixin
from hsr_version_inspector.pdf.show import PdfShowMixin


class RefactorContractTests(unittest.TestCase):
    def test_diff_compatibility_exports_use_the_new_models(self) -> None:
        self.assertIs(CharacterChange, ModelCharacterChange)
        self.assertEqual(
            tokenize_text_diff("伤害10%", "伤害20%"),
            model_tokenize_text_diff("伤害10%", "伤害20%"),
        )

    def test_download_compatibility_exports_use_the_new_model(self) -> None:
        self.assertIs(DownloadTarget, ModelDownloadTarget)
        target = DownloadTarget("4.4.54", "story", "2026")
        self.assertEqual(target.relative_path.as_posix(), "4.4.54/zh/story/2026.json")

    def test_pdf_renderer_keeps_component_boundaries(self) -> None:
        self.assertTrue(issubclass(PdfRenderer, PdfShowMixin))
        self.assertTrue(issubclass(PdfRenderer, PdfDiffMixin))


if __name__ == "__main__":
    unittest.main()
