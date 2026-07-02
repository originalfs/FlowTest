from localflow.cleanup import (
    apply_dictionary,
    capitalize_sentences,
    clean,
    normalize_whitespace,
    remove_fillers,
)


class TestRemoveFillers:
    def test_removes_standalone_fillers(self):
        assert remove_fillers("um so I was uh thinking") == "so I was thinking"

    def test_removes_filler_with_trailing_comma(self):
        assert remove_fillers("Um, let's start.") == "let's start."

    def test_leading_comma_left_by_filler_is_dropped(self):
        assert remove_fillers("Uh, yes.") == "yes."

    def test_keeps_words_containing_fillers(self):
        assert remove_fillers("the drummer hummed") == "the drummer hummed"

    def test_does_not_strip_meaningful_like(self):
        assert remove_fillers("I like pizza") == "I like pizza"

    def test_case_insensitive(self):
        assert remove_fillers("UM hello UHH world") == "hello world"


class TestDictionary:
    def test_basic_replacement(self):
        assert apply_dictionary("open local flow now", {"local flow": "LocalFlow"}) == (
            "open LocalFlow now"
        )

    def test_case_insensitive_match(self):
        assert apply_dictionary("Local Flow rocks", {"local flow": "LocalFlow"}) == (
            "LocalFlow rocks"
        )

    def test_longest_match_wins(self):
        d = {"flow": "FLOW", "local flow": "LocalFlow"}
        assert apply_dictionary("local flow", d) == "LocalFlow"

    def test_word_boundaries(self):
        assert apply_dictionary("workflow", {"flow": "FLOW"}) == "workflow"


class TestNormalizeAndCapitalize:
    def test_collapses_spaces(self):
        assert normalize_whitespace("a   b\t c ") == "a b c"

    def test_preserves_newlines(self):
        assert normalize_whitespace("a \n b") == "a\nb"

    def test_capitalizes_sentence_starts(self):
        assert capitalize_sentences("hello. world! how? yes") == "Hello. World! How? Yes"


class TestClean:
    def test_full_pipeline(self):
        raw = "um so,  i think local flow is uh ready.  let's ship it"
        out = clean(raw, dictionary={"local flow": "LocalFlow"})
        assert out == "So, i think LocalFlow is ready. Let's ship it"

    def test_empty_input(self):
        assert clean("") == ""

    def test_only_fillers(self):
        assert clean("um uh umm") == ""

    def test_flags_off(self):
        raw = "um hello"
        assert clean(raw, remove_filler_words=False, capitalize=False) == "um hello"
