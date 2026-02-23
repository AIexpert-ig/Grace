from app.main import _has_pricing_keyword


def test_pricing_keyword_matches_whole_word_room():
    assert _has_pricing_keyword("room") is True
    assert _has_pricing_keyword("rooms") is True
    assert _has_pricing_keyword("room rates") is True


def test_pricing_keyword_matches_rates_variants():
    assert _has_pricing_keyword("rates please") is True
    assert _has_pricing_keyword("what is the price") is True
    assert _has_pricing_keyword("pricing info") is True
    assert _has_pricing_keyword("what does it cost") is True


def test_pricing_keyword_does_not_match_substrings():
    assert _has_pricing_keyword("bathroom") is False
    assert _has_pricing_keyword("roomservice") is False
    assert _has_pricing_keyword("showroom") is False
    assert _has_pricing_keyword("groom") is False


def test_pricing_keyword_handles_punctuation():
    assert _has_pricing_keyword("Room?") is True
    assert _has_pricing_keyword("Rates.") is True

