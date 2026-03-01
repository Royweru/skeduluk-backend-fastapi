import asyncio
import os
import uuid
from typing import Optional, List
from pathlib import Path
from openai import AsyncOpenAI
import aiohttp
import aiofiles

from ...config import settings


class TTSService:
    AVAILABLE_VOICES = {
        "openai": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
        "edge_tts": [
            "en-US-AriaNeural",
            "en-US-GuyNeural",
            "en-GB-SoniaNeural",
            "en-AU-NatashaNeural",
            "en-CA-ClaraNeural",
        ],
    }

    def __init__(self):
        self.openai_client = (
            AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            if settings.OPENAI_API_KEY
            else None
        )
        self.output_dir = Path(settings.VIDEO_TEMP_DIR) / "audio"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate_speech_openai(
        self, text: str, voice: str = "alloy", speed: float = 1.0, model: str = "tts-1"
    ) -> tuple[str, float]:
        if not self.openai_client:
            raise ValueError("OpenAI API key not configured")

        if voice not in self.AVAILABLE_VOICES["openai"]:
            voice = "alloy"

        response = await self.openai_client.audio.speech.create(
            model=model, voice=voice, input=text, speed=speed, response_format="mp3"
        )

        audio_filename = f"tts_{uuid.uuid4().hex}.mp3"
        audio_path = self.output_dir / audio_filename

        async with aiofiles.open(audio_path, "wb") as f:
            await f.write(response.content)

        duration = await self._get_audio_duration(str(audio_path))

        return str(audio_path), duration

    async def generate_speech_edge_tts(
        self, text: str, voice: str = "en-US-AriaNeural", speed: float = 1.0
    ) -> tuple[str, float]:
        try:
            import edge_tts
        except ImportError:
            raise ImportError("edge-tts not installed. Run: pip install edge-tts")

        communicate = edge_tts.Communicate(
            text, voice, rate=f"+{int((speed - 1) * 100)}%"
        )

        audio_filename = f"tts_edge_{uuid.uuid4().hex}.mp3"
        audio_path = self.output_dir / audio_filename

        await communicate.save(str(audio_path))

        duration = await self._get_audio_duration(str(audio_path))

        return str(audio_path), duration

    async def generate_narration(
        self,
        text: str,
        provider: str = "openai",
        voice: Optional[str] = None,
        speed: float = 1.0,
    ) -> dict:
        if provider == "openai":
            voice = voice or "alloy"
            audio_path, duration = await self.generate_speech_openai(
                text=text, voice=voice, speed=speed
            )
        elif provider == "edge_tts":
            voice = voice or "en-US-AriaNeural"
            audio_path, duration = await self.generate_speech_edge_tts(
                text=text, voice=voice, speed=speed
            )
        else:
            raise ValueError(f"Unknown TTS provider: {provider}")

        return {
            "audio_path": audio_path,
            "duration": duration,
            "provider": provider,
            "voice": voice,
        }

    async def generate_scene_narrations(
        self,
        scenes: List[dict],
        provider: str = "openai",
        voice: str = "alloy",
        speed: float = 1.0,
    ) -> List[dict]:
        results = []

        for scene in scenes:
            narration_text = scene.get("narration", "") or scene.get("text", "")

            if not narration_text:
                results.append(
                    {
                        "scene_index": scene.get("index", 0),
                        "audio_path": None,
                        "duration": 0,
                    }
                )
                continue

            narration = await self.generate_narration(
                text=narration_text, provider=provider, voice=voice, speed=speed
            )

            results.append(
                {
                    "scene_index": scene.get("index", 0),
                    "audio_path": narration["audio_path"],
                    "duration": narration["duration"],
                }
            )

        return results

    async def _get_audio_duration(self, audio_path: str) -> float:
        try:
            from pydub import AudioSegment

            audio = AudioSegment.from_mp3(audio_path)
            return len(audio) / 1000.0
        except Exception as e:
            print(f"Error getting audio duration: {e}")
            char_count = 0
            try:
                async with aiofiles.open(audio_path, "rb") as f:
                    content = await f.read()
                    char_count = len(content) / 100
            except:
                pass
            return char_count / 15

    def get_available_voices(self, provider: str = "openai") -> List[str]:
        return self.AVAILABLE_VOICES.get(provider, [])


tts_service = TTSService()
