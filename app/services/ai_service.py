# app/services/ai_service.py
import os
from typing import Dict, List, Optional
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from google import genai
from google.genai import types
from groq import AsyncGroq
import asyncio
from dotenv import load_dotenv

load_dotenv()


class AIService:
    """
    AI Service for content enhancement using multiple providers
    Supports: Groq (fast inference), Google Gemini 2.5, OpenAI GPT-4, Anthropic Claude, X.AI Grok
    """
    
    def __init__(self):
        self.openai_client = None
        self.anthropic_client = None
        self.gemini_client = None
        self.groq_client = None
        self.grok_client = None
        self.provider = os.getenv("AI_PROVIDER", "groq").lower()
        
        # Initialize clients based on available API keys
        groq_key = os.getenv("GROQ_API_KEY")
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        grok_key = os.getenv("XAI_API_KEY")
        
        # Initialize Groq (OpenAI-compatible, very fast)
        if groq_key:
            self.groq_client = AsyncGroq(api_key=groq_key)
            print("✓ Groq client initialized")
        
        # Initialize Google Gemini 2.5 (NEW SDK)
        if gemini_key:
            try:
                self.gemini_client = genai.Client(api_key=gemini_key)
                print("✓ Google Gemini client initialized")
            except Exception as e:
                print(f"Failed to initialize Gemini: {e}")
        
        # Initialize OpenAI
        if openai_key:
            self.openai_client = AsyncOpenAI(api_key=openai_key)
            print("✓ OpenAI client initialized")
        
        # Initialize Anthropic Claude
        if anthropic_key:
            self.anthropic_client = AsyncAnthropic(api_key=anthropic_key)
            print("✓ Anthropic client initialized")
        
        # Initialize Grok (X.AI)
        if grok_key:
            self.grok_client = AsyncOpenAI(
                api_key=grok_key,
                base_url="https://api.x.ai/v1"
            )
            print("✓ Grok client initialized")
        
        # Platform character limits
        self.platform_limits = {
            "TWITTER": 280,
            "LINKEDIN": 3000,
            "FACEBOOK": 63206,
            "INSTAGRAM": 2200
        }
        
        # Platform-specific tone guidelines
        self.platform_tones = {
            "TWITTER": "concise, punchy, and engaging with strategic hashtags",
            "LINKEDIN": "professional, thoughtful, and value-driven",
            "FACEBOOK": "conversational, friendly, and community-focused",
            "INSTAGRAM": "visual-first, casual, and emoji-friendly"
        }
    
    async def enhance_content(
        self,
        content: str,
        platform: str,
        tone: str = "engaging",
        image_count: int = 0,
        include_hashtags: bool = True,
        include_emojis: bool = False
    ) -> str:
        """
        Enhance content for a specific platform using AI
        
        Args:
            content: Original content to enhance
            platform: Target platform (TWITTER, LINKEDIN, FACEBOOK, INSTAGRAM)
            tone: Desired tone (engaging, professional, casual, humorous, inspirational)
            image_count: Number of images to suggest
            include_hashtags: Whether to include relevant hashtags
            include_emojis: Whether to include emojis
        
        Returns:
            Enhanced content optimized for the platform
        """
        platform = platform.upper()
        char_limit = self.platform_limits.get(platform, 3000)
        platform_tone = self.platform_tones.get(platform, "engaging and appropriate")
        
        # Build the enhancement prompt
        prompt = self._build_enhancement_prompt(
            content=content,
            platform=platform,
            platform_tone=platform_tone,
            tone=tone,
            char_limit=char_limit,
            include_hashtags=include_hashtags,
            include_emojis=include_emojis,
            image_count=image_count
        )
        
        # Try providers in order of preference
        providers = self._get_available_providers()
        
        for provider_name in providers:
            try:
                print(f"Trying provider: {provider_name}")
                
                if provider_name == "groq" and self.groq_client:
                    return await self._enhance_with_groq(prompt, char_limit)
                elif provider_name == "gemini" and self.gemini_client:
                    return await self._enhance_with_gemini(prompt, char_limit)
                elif provider_name == "openai" and self.openai_client:
                    return await self._enhance_with_openai(prompt, char_limit)
                elif provider_name == "anthropic" and self.anthropic_client:
                    return await self._enhance_with_anthropic(prompt, char_limit)
                elif provider_name == "grok" and self.grok_client:
                    return await self._enhance_with_grok(prompt, char_limit)
                    
            except Exception as e:
                print(f"Error with {provider_name}: {e}, trying next provider...")
                continue
        
        # All AI providers failed, use basic enhancement
        print("All AI providers failed, using basic enhancement")
        return await self._basic_enhancement(content, platform, char_limit)
    
    def _get_available_providers(self) -> List[str]:
        """Get list of available providers, prioritizing the configured one"""
        available = []
        
        # Add configured provider first
        if self.provider == "groq" and self.groq_client:
            available.append("groq")
        elif self.provider == "gemini" and self.gemini_client:
            available.append("gemini")
        elif self.provider == "openai" and self.openai_client:
            available.append("openai")
        elif self.provider == "anthropic" and self.anthropic_client:
            available.append("anthropic")
        elif self.provider == "grok" and self.grok_client:
            available.append("grok")
        
        # Add other available providers as fallbacks
        if "groq" not in available and self.groq_client:
            available.append("groq")
        if "gemini" not in available and self.gemini_client:
            available.append("gemini")
        if "openai" not in available and self.openai_client:
            available.append("openai")
        if "anthropic" not in available and self.anthropic_client:
            available.append("anthropic")
        if "grok" not in available and self.grok_client:
            available.append("grok")
        
        return available
    
    def _build_enhancement_prompt(
        self,
        content: str,
        platform: str,
        platform_tone: str,
        tone: str,
        char_limit: int,
        include_hashtags: bool,
        include_emojis: bool,
        image_count: int
    ) -> str:
        """Build the AI prompt for content enhancement"""
        
        hashtag_instruction = "Include 3-5 relevant hashtags." if include_hashtags else "Do not include hashtags."
        emoji_instruction = "Include relevant emojis to enhance engagement." if include_emojis else "Do not include emojis."
        
        prompt = f"""You are a professional social media content writer. Enhance the following content for {platform}.

Original Content:
{content}

Requirements:
- Platform: {platform}
- Character Limit: Stay under {char_limit} characters
- Tone: {tone} and {platform_tone}
- {hashtag_instruction}
- {emoji_instruction}

Additional Guidelines:
- Make it engaging and authentic
- Optimize for platform algorithm (engagement-focused)
- Include a clear call-to-action if appropriate
- Ensure it sounds natural, not robotic
- For Twitter: Be concise and impactful
- For LinkedIn: Be professional and insightful
- For Facebook: Be conversational and community-focused
- For Instagram: Be visual-first and use line breaks

Return ONLY the enhanced content, nothing else. No explanations or meta-commentary."""

        if image_count > 0:
            prompt += f"\n- Optionally suggest {image_count} image ideas"
        
        return prompt
    
    async def _enhance_with_groq(self, prompt: str, char_limit: int) -> str:
        """Enhance content using Groq (fastest inference)"""
        response = await self.groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Fast and capable
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert social media content creator. Create engaging, authentic content optimized for each platform."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=min(char_limit + 300, 4000)
        )
        
        return response.choices[0].message.content.strip()
    
    async def _enhance_with_gemini(self, prompt: str, char_limit: int) -> str:
        """Enhance content using Google Gemini 2.5 (NEW SDK)"""
        # Gemini API is synchronous, run in thread pool
        def generate():
            response = self.gemini_client.models.generate_content(
                model='gemini-2.5-flash',  # Fast and efficient
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=min(char_limit + 300, 8000),
                    system_instruction="You are an expert social media content creator. Create engaging, authentic content optimized for each platform."
                )
            )
            return response.text.strip()
        
        result = await asyncio.to_thread(generate)
        return result
    
    async def _enhance_with_openai(self, prompt: str, char_limit: int) -> str:
        """Enhance content using OpenAI GPT-4"""
        response = await self.openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert social media content creator. Create engaging, authentic content optimized for each platform."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=min(char_limit + 300, 4000)
        )
        
        return response.choices[0].message.content.strip()
    
    async def _enhance_with_anthropic(self, prompt: str, char_limit: int) -> str:
        """Enhance content using Anthropic Claude"""
        message = await self.anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=min(char_limit + 300, 4000),
            temperature=0.7,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        return message.content[0].text.strip()
    
    async def _enhance_with_grok(self, prompt: str, char_limit: int) -> str:
        """Enhance content using X.AI Grok"""
        response = await self.grok_client.chat.completions.create(
            model="grok-beta",
            messages=[
                {
                    "role": "system",
                    "content": "You are Grok, a witty and insightful AI assistant. Create engaging social media content with personality."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.8,
            max_tokens=min(char_limit + 300, 4000)
        )
        
        return response.choices[0].message.content.strip()
    
    async def _basic_enhancement(self, content: str, platform: str, char_limit: int) -> str:
        """Basic enhancement when no AI provider is available"""
        enhanced = content.strip()
        
        # Truncate if too long
        if len(enhanced) > char_limit - 50:
            enhanced = enhanced[:char_limit - 50] + "..."
        
        # Add platform-specific touches
        if platform == "TWITTER":
            if "#" not in enhanced:
                enhanced += " #SocialMedia"
        elif platform == "LINKEDIN":
            if "?" not in enhanced:
                enhanced += "\n\nWhat are your thoughts?"
        
        return enhanced
    
    async def generate_hashtags(self, content: str, count: int = 5) -> List[str]:
        """Generate relevant hashtags for content"""
        prompt = f"""Generate {count} relevant and trending hashtags for this social media post. Return ONLY the hashtags, one per line, with the # symbol.

Content: {content}

Hashtags:"""
        
        try:
            # Try with primary provider
            if self.groq_client:
                response = await self.groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                    max_tokens=100
                )
                hashtags_text = response.choices[0].message.content.strip()
            elif self.gemini_client:
                def generate():
                    response = self.gemini_client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.5,
                            max_output_tokens=100
                        )
                    )
                    return response.text.strip()
                hashtags_text = await asyncio.to_thread(generate)
            elif self.openai_client:
                response = await self.openai_client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                    max_tokens=100
                )
                hashtags_text = response.choices[0].message.content.strip()
            elif self.anthropic_client:
                message = await self.anthropic_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=100,
                    messages=[{"role": "user", "content": prompt}]
                )
                hashtags_text = message.content[0].text.strip()
            else:
                return ["#SocialMedia", "#Content", "#Digital"]
            
            # Parse hashtags
            hashtags = [line.strip() for line in hashtags_text.split("\n") if line.strip().startswith("#")]
            return hashtags[:count]
        
        except Exception as e:
            print(f"Hashtag generation error: {e}")
            return ["#SocialMedia", "#Content", "#Digital"]
    
    async def suggest_post_time(self, platform: str, timezone: str = "UTC") -> Dict[str, str]:
        """Suggest optimal posting time for a platform"""
        best_times = {
            "TWITTER": {"day": "Wednesday", "time": "09:00 AM - 12:00 PM"},
            "LINKEDIN": {"day": "Tuesday-Thursday", "time": "08:00 AM - 10:00 AM"},
            "FACEBOOK": {"day": "Wednesday-Thursday", "time": "01:00 PM - 03:00 PM"},
            "INSTAGRAM": {"day": "Wednesday", "time": "11:00 AM - 01:00 PM"}
        }
        
        return best_times.get(platform.upper(), {"day": "Weekday", "time": "09:00 AM - 05:00 PM"})
    
    def get_provider_info(self) -> Dict[str, bool]:
        """Get information about available AI providers"""
        return {
            "groq": self.groq_client is not None,
            "gemini": self.gemini_client is not None,
            "openai": self.openai_client is not None,
            "anthropic": self.anthropic_client is not None,
            "grok": self.grok_client is not None,
            "configured_provider": self.provider
        }


# Singleton instance
ai_service = AIService()