from long_term_excel import LongTermWorkbookManager


class NormalRange:
    def __init__(self):
        self.clear_calls = 0
        self.unmerge_calls = 0

    def ClearContents(self):
        self.clear_calls += 1

    def UnMerge(self):
        self.unmerge_calls += 1


class MergedRange:
    def __init__(self):
        self.clear_calls = 0
        self.unmerge_calls = 0

    def ClearContents(self):
        self.clear_calls += 1
        if self.clear_calls == 1:
            raise RuntimeError(
                "We can't do that to a merged cell."
            )

    def UnMerge(self):
        self.unmerge_calls += 1


def test_safe_clear_uses_normal_clear_when_no_merge_exists():
    target = NormalRange()
    LongTermWorkbookManager._clear_contents_safely(target)

    assert target.clear_calls == 1
    assert target.unmerge_calls == 0


def test_safe_clear_unmerges_and_retries_after_excel_merge_error():
    target = MergedRange()
    LongTermWorkbookManager._clear_contents_safely(target)

    assert target.clear_calls == 2
    assert target.unmerge_calls == 1
