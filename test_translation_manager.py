# test_translation_manager.py
import pytest


@pytest.mark.asyncio
async def default_test_get_translation(trader):
    translation_manager = trader.translation_manager
    translation = translation_manager.get_translation("current_language")
    assert translation == "English"


@pytest.mark.asyncio
async def test_get_en_translation(trader):
    translation_manager = trader.translation_manager
    translation = translation_manager.get_translation("current_language", "en")
    assert translation == "English"


@pytest.mark.asyncio
async def test_get_known_translation(trader):
    translation_manager = trader.translation_manager
    translation = translation_manager.get_translation("current_language", "fr")
    assert translation == "Français"


@pytest.mark.asyncio
async def test_get_untranslated_translation(trader):
    translation_manager = trader.translation_manager
    translation = translation_manager.get_translation("untranslated", "fr")
    assert translation == "Test Untranslated"


@pytest.mark.asyncio
async def test_get_unknown_translation(trader):
    translation_manager = trader.translation_manager
    translation = translation_manager.get_translation("unknown_translation")
    assert translation == "unknown_translation"


@pytest.mark.asyncio
async def test_get_available_languages(trader):
    translation_manager = trader.translation_manager
    languages = translation_manager.get_available_lang()
    assert len(languages) > 0


@pytest.mark.asyncio
async def test_get_language_name(trader):
    translation_manager = trader.translation_manager
    language_name = translation_manager.get_lang_name("en")
    assert language_name == "English"
