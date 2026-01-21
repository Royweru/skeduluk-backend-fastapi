# app/services/transcription_service.py
import os
import io
import httpx
import tempfile
from typing import Optional, Dict, Any, BinaryIO
from openai import AsyncOpenAI
from fastapi import UploadFile

from ..config import settings


class TranscriptionService:
    """
    Professional audio transcription service using OpenAI Whisper API
    Supports multiple audio formats and provides robust error handling
    """

    def __init__(self):
        """Initialize OpenAI client for Whisper API"""
        self.openai_api_key = os.getenv(
            "OPENAI_API_KEY") or settings.OPENAI_API_KEY
        if not self.openai_api_key:
            print("⚠️ WARNING: OPENAI_API_KEY not configured. Transcription will fail.")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=self.openai_api_key)
            print("✅ OpenAI Whisper transcription service initialized")

    async def transcribe_file(
        self,
        audio_file: UploadFile,
        language: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribe an uploaded audio file using OpenAI Whisper

        Args:
            audio_file: FastAPI UploadFile object
            language: Optional ISO-639-1 language code (e.g., 'en', 'es')
            prompt: Optional text to guide the model's style

        Returns:
            Dict containing transcription text and metadata

        Raises:
            Exception: If OpenAI API key is not configured or transcription fails
        """
        if not self.client:
            raise Exception(
                "OpenAI API key not configured. Please set OPENAI_API_KEY in environment variables.")

        try:
            # Validate file type
            allowed_formats = ['webm', 'mp3', 'wav', 'm4a',
                               'ogg', 'flac', 'mp4', 'mpeg', 'mpga']
            file_extension = audio_file.filename.split(
                '.')[-1].lower() if audio_file.filename else 'webm'

            if file_extension not in allowed_formats:
                raise ValueError(
                    f"Unsupported audio format: {file_extension}. Supported: {', '.join(allowed_formats)}")

            # Read file content
            audio_content = await audio_file.read()

            # Create a temporary file with proper extension
            with tempfile.NamedTemporaryFile(suffix=f'.{file_extension}', delete=False) as temp_file:
                temp_file.write(audio_content)
                temp_file_path = temp_file.name

            try:
                # Transcribe using OpenAI Whisper API
                print(
                    f"🎙️ Transcribing audio file ({len(audio_content)} bytes, format: {file_extension})...")

                with open(temp_file_path, "rb") as audio:
                    transcript = await self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio,
                        language=language,
                        prompt=prompt,
                        response_format="verbose_json"  # Get detailed response
                    )

                print(
                    f"✅ Transcription completed: {len(transcript.text)} characters")

                return {
                    "text": transcript.text,
                    "language": transcript.language if hasattr(transcript, 'language') else None,
                    "duration": transcript.duration if hasattr(transcript, 'duration') else None
                }

            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        except Exception as e:
            print(f"❌ Transcription error: {str(e)}")
            raise Exception(f"Transcription failed: {str(e)}")

    async def transcribe_from_url(
        self,
        audio_url: str,
        language: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribe audio from a URL using OpenAI Whisper

        Args:
            audio_url: URL to the audio file
            language: Optional ISO-639-1 language code
            prompt: Optional text to guide the model's style

        Returns:
            Dict containing transcription text and metadata

        Raises:
            Exception: If download fails or transcription fails
        """
        if not self.client:
            raise Exception(
                "OpenAI API key not configured. Please set OPENAI_API_KEY in environment variables.")

        try:
            # Download audio file
            print(f"📥 Downloading audio from URL: {audio_url}")
            async with httpx.AsyncClient(timeout=30.0) as http_client:
                response = await http_client.get(audio_url)

                if response.status_code != 200:
                    raise Exception(
                        f"Failed to download audio file: HTTP {response.status_code}")

                audio_data = response.content

            # Determine file extension from URL
            file_extension = os.path.splitext(audio_url)[1].lower().lstrip('.')
            if not file_extension or file_extension not in ['webm', 'mp3', 'wav', 'm4a', 'ogg', 'flac']:
                file_extension = 'webm'  # Default format

            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix=f'.{file_extension}', delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name

            try:
                # Transcribe using OpenAI Whisper
                print(
                    f"🎙️ Transcribing audio from URL ({len(audio_data)} bytes)...")

                with open(temp_file_path, "rb") as audio:
                    transcript = await self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio,
                        language=language,
                        prompt=prompt,
                        response_format="verbose_json"
                    )

                print(
                    f"✅ Transcription completed: {len(transcript.text)} characters")

                return {
                    "text": transcript.text,
                    "language": transcript.language if hasattr(transcript, 'language') else None,
                    "duration": transcript.duration if hasattr(transcript, 'duration') else None
                }

            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        except Exception as e:
            print(f"❌ Transcription from URL failed: {str(e)}")
            raise Exception(f"Transcription from URL failed: {str(e)}")


# Singleton instance
transcription_service = TranscriptionService()
