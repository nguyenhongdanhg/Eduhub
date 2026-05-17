import os
import unittest
from unittest import mock


class TestIOfficeAudioTts(unittest.TestCase):
  def test_auto_falls_back_to_openai(self):
    from app.services import ioffice_audio

    os.environ["EDUAI_IOFFICE_AUDIO_PROVIDER"] = "auto"

    with (
      mock.patch.object(ioffice_audio, "_get_google_tts_key", return_value=""),
      mock.patch.object(ioffice_audio, "edge_tts_mp3", side_effect=RuntimeError("no_edge")),
      mock.patch.object(ioffice_audio, "gtts_mp3", side_effect=RuntimeError("no_gtts")),
      mock.patch.object(ioffice_audio, "sapi_tts_wav", side_effect=RuntimeError("no_sapi")),
      mock.patch.object(ioffice_audio, "tts_available", return_value=True),
      mock.patch.object(ioffice_audio, "_tts_openai_mp3", return_value=b"mp3data") as m_openai,
    ):
      audio, ext = ioffice_audio._tts_audio("xin chào")
      self.assertEqual(audio, b"mp3data")
      self.assertEqual(ext, "mp3")
      self.assertTrue(m_openai.called)

  def test_provider_openai_uses_openai_directly(self):
    from app.services import ioffice_audio

    os.environ["EDUAI_IOFFICE_AUDIO_PROVIDER"] = "openai"

    with (
      mock.patch.object(ioffice_audio, "_tts_openai_mp3", return_value=b"x") as m_openai,
      mock.patch.object(ioffice_audio, "edge_tts_mp3", side_effect=AssertionError("should not call")),
      mock.patch.object(ioffice_audio, "gtts_mp3", side_effect=AssertionError("should not call")),
      mock.patch.object(ioffice_audio, "sapi_tts_wav", side_effect=AssertionError("should not call")),
    ):
      audio, ext = ioffice_audio._tts_audio("a")
      self.assertEqual(audio, b"x")
      self.assertEqual(ext, "mp3")
      self.assertTrue(m_openai.called)

  def test_auto_unavailable_message_is_helpful(self):
    from app.services import ioffice_audio

    os.environ["EDUAI_IOFFICE_AUDIO_PROVIDER"] = "auto"

    with (
      mock.patch.object(ioffice_audio, "_get_google_tts_key", return_value=""),
      mock.patch.object(ioffice_audio, "edge_tts_mp3", side_effect=RuntimeError("no_edge")),
      mock.patch.object(ioffice_audio, "gtts_mp3", side_effect=RuntimeError("no_gtts")),
      mock.patch.object(ioffice_audio, "sapi_tts_wav", side_effect=RuntimeError("no_sapi")),
      mock.patch.object(ioffice_audio, "tts_available", return_value=False),
    ):
      with self.assertRaises(RuntimeError) as ctx:
        ioffice_audio._tts_audio("a")
      msg = str(ctx.exception)
      self.assertIn("TTS không khả dụng", msg)
      self.assertIn("openai(not_configured)", msg)


if __name__ == "__main__":
  unittest.main()

