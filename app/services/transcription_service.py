# app/services/transcription_service.py
import os
import io
import httpx
from typing import Optional

from ..config import settings

class TranscriptionService:
    @staticmethod
    async def transcribe(audio_file_url: str) -> Optional[str]:
        """Transcribe audio file to text using OpenAI Whisper"""
        try:
            # Download audio file
            async with httpx.AsyncClient() as client:
                response = await client.get(audio_file_url)
                if response.status_code != 200:
                    print(f"Failed to download audio file: {response.status_code}")
                    return None
                
                audio_data = response.content
            
            # Create a file-like object from the audio data
            audio_file = io.BytesIO(audio_data)
            
            # Determine file extension from URL
            file_extension = os.path.splitext(audio_file_url)[1].lower()
            
            # Create a temporary file with the correct extension
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            try:
                # Transcribe using OpenAI Whisper
                with open(temp_file_path, "rb") as audio:
                    transcript = await openai.Audio.atranscribe(
                        model="whisper-1",
                        file=audio
                    )
                
                return transcript["text"]
            
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)
                
        except Exception as e:
            print(f"Transcription failed: {e}")
            return None