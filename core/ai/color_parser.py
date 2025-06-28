"""
AI-enhanced color parsing using PydanticAI.
"""

import logging
import re
import time
from typing import Optional, Tuple

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from utils.ai.interpretability import FeatureExtractor, log_and_explain

from ..models.command import ColorInput

logger = logging.getLogger(__name__)


class EnhancedColorInput(BaseModel):
    """Enhanced color with AI interpretation."""

    raw_input: str
    hex_color: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")
    rgb: Tuple[int, int, int]
    discord_color: int
    confidence: float = Field(..., ge=0, le=1)
    interpretation: str
    closest_named_color: Optional[str] = None

    @classmethod
    def from_color_input(
        cls, color: ColorInput, interpretation: str = "", confidence: float = 1.0, closest_named: Optional[str] = None
    ) -> "EnhancedColorInput":
        """Create from basic ColorInput."""
        return cls(
            raw_input=color.raw_input,
            hex_color=color.hex_color,
            rgb=color.rgb,
            discord_color=color.discord_color,
            confidence=confidence,
            interpretation=interpretation,
            closest_named_color=closest_named,
        )


class ColorParser:
    """AI-powered color parser for natural language descriptions."""

    # Extended color database (Polish)
    NAMED_COLORS = {
        # Basic colors - English
        "red": "#FF0000",
        "green": "#00FF00",
        "blue": "#0000FF",
        "yellow": "#FFFF00",
        "purple": "#800080",
        "orange": "#FFA500",
        "pink": "#FFC0CB",
        "black": "#000000",
        "white": "#FFFFFF",
        "gray": "#808080",
        "grey": "#808080",
        # Basic colors - Polish
        "czerwony": "#FF0000",
        "zielony": "#00FF00",
        "niebieski": "#0000FF",
        "żółty": "#FFFF00",
        "fioletowy": "#800080",
        "pomarańczowy": "#FFA500",
        "różowy": "#FFC0CB",
        "czarny": "#000000",
        "biały": "#FFFFFF",
        "szary": "#808080",
        # Discord brand colors
        "discord": "#5865F2",
        "discord blue": "#5865F2",
        "blurple": "#5865F2",
        # Social media colors
        "twitch": "#9146FF",
        "twitch purple": "#9146FF",
        "youtube": "#FF0000",
        "youtube red": "#FF0000",
        "twitter": "#1DA1F2",
        "twitter blue": "#1DA1F2",
        "facebook": "#1877F2",
        "instagram": "#E4405F",
        "spotify": "#1DB954",
        "spotify green": "#1DB954",
        # Additional colors - English
        "cyan": "#00FFFF",
        "magenta": "#FF00FF",
        "lime": "#00FF00",
        "navy": "#000080",
        "teal": "#008080",
        "silver": "#C0C0C0",
        "gold": "#FFD700",
        "brown": "#A52A2A",
        "beige": "#F5F5DC",
        "mint": "#3EB489",
        "lavender": "#E6E6FA",
        "coral": "#FF7F50",
        "salmon": "#FA8072",
        "crimson": "#DC143C",
        "indigo": "#4B0082",
        "violet": "#EE82EE",
        "turquoise": "#40E0D0",
        # Additional colors - Polish
        "cyjan": "#00FFFF",
        "turkusowy": "#40E0D0",
        "magenta": "#FF00FF",
        "limonkowy": "#00FF00",
        "granatowy": "#000080",
        "morski": "#008080",
        "srebrny": "#C0C0C0",
        "złoty": "#FFD700",
        "brązowy": "#A52A2A",
        "beżowy": "#F5F5DC",
        "miętowy": "#3EB489",
        "lawendowy": "#E6E6FA",
        "koralowy": "#FF7F50",
        "łososiowy": "#FA8072",
        "karmazynowy": "#DC143C",
        "indygo": "#4B0082",
    }

    def __init__(self, use_ai: bool = True):
        """Initialize parser with optional AI support."""
        self.use_ai = use_ai

        if use_ai:
            import os

            # Pobierz klucz API z zmiennych środowiskowych - Gemini jako priorytet
            gemini_key = os.getenv("GEMINI_API_KEY")
            openai_key = os.getenv("OPENAI_API_KEY")

            system_prompt = """Jesteś parserem kolorów dla polskiego bota Discord.
                Konwertuj naturalne opisy kolorów na kody hex.

                Przykłady:
                - "ciemny niebieski" -> "#00008B"
                - "jasny fioletowy" -> "#DDA0DD"
                - "morski" -> "#006994"
                - "pomarańczowy zachód słońca" -> "#FD5E53"
                - "kolor discorda" -> "#5865F2"
                - "trochę ciemniejszy niż różowy" -> "#FFB6C1"

                Zawsze odpowiadaj tylko kodem hex w formacie #RRGGBB.
                Dla kolorów marek, używaj ich oficjalnych kolorów.
                Dla opisowych kolorów, wybierz najbardziej odpowiedni odcień."""

            if gemini_key:
                # Set API key in environment for pydantic-ai
                import os

                os.environ["GOOGLE_API_KEY"] = gemini_key
                self.agent = Agent("gemini-1.5-flash", system_prompt=system_prompt)  # Darmowy do 1M tokenów/miesiąc!
                logger.info("Using Google Gemini for AI color parsing (free tier)")
            elif openai_key:
                # Set API key in environment for pydantic-ai
                import os

                os.environ["OPENAI_API_KEY"] = openai_key
                self.agent = Agent("openai:gpt-3.5-turbo", system_prompt=system_prompt)
                logger.info("Using OpenAI for AI color parsing")
            else:
                logger.warning("No API key found (GEMINI_API_KEY or OPENAI_API_KEY), AI features will be disabled")
                self.use_ai = False

    async def parse(self, color_str: str) -> EnhancedColorInput:
        """Parse color string with AI enhancement."""
        start_time = time.time()
        color_str = color_str.strip()

        # Extract features for interpretability
        features = await FeatureExtractor.extract_color_features(color_str)

        # First try traditional parsing
        try:
            basic_color = self._parse_traditional(color_str)
            if basic_color:
                # Log successful traditional parsing
                execution_time = (time.time() - start_time) * 1000
                await log_and_explain(
                    module="color_parser",
                    input_data={"text": color_str},
                    features=features,
                    output=basic_color.hex_color,
                    decision=basic_color.hex_color,
                    confidence=1.0,
                    reasoning="Standard hex/RGB format",
                    execution_time_ms=execution_time,
                )

                return EnhancedColorInput.from_color_input(
                    basic_color, interpretation="Standardowy format", confidence=1.0
                )
        except Exception:
            pass

        # Try named colors
        lower_str = color_str.lower()
        if lower_str in self.NAMED_COLORS:
            basic_color = ColorInput.parse(self.NAMED_COLORS[lower_str])

            # Log named color match
            execution_time = (time.time() - start_time) * 1000
            await log_and_explain(
                module="color_parser",
                input_data={"text": color_str},
                features=features,
                output=self.NAMED_COLORS[lower_str],
                decision=self.NAMED_COLORS[lower_str],
                confidence=1.0,
                reasoning=f"Named color match: {lower_str}",
                execution_time_ms=execution_time,
            )

            return EnhancedColorInput.from_color_input(
                basic_color, interpretation=f"Rozpoznany kolor: {lower_str}", confidence=1.0, closest_named=lower_str
            )

        # If traditional parsing fails and AI is enabled, use AI
        if self.use_ai:
            return await self._parse_with_ai(color_str, features, start_time)
        else:
            raise ValueError(f"Cannot parse color: {color_str}")

    def _parse_traditional(self, color_str: str) -> Optional[ColorInput]:
        """Traditional parsing for hex and RGB formats."""
        # Try to parse using the basic ColorInput parser
        try:
            return ColorInput.parse(color_str)
        except Exception:
            return None

    async def _parse_with_ai(
        self, color_str: str, features: Optional[dict] = None, start_time: Optional[float] = None
    ) -> EnhancedColorInput:
        """Parse using AI for natural language understanding."""
        if start_time is None:
            start_time = time.time()
        if features is None:
            features = await FeatureExtractor.extract_color_features(color_str)

        try:
            # Get AI interpretation
            result = await self.agent.run(f"Konwertuj ten opis koloru na hex: '{color_str}'")

            # Extract hex code from response
            hex_match = re.search(r"#[0-9A-Fa-f]{6}", result.data)
            if not hex_match:
                raise ValueError("AI didn't return valid hex code")

            hex_color = hex_match.group(0).upper()

            # Create ColorInput from hex
            basic_color = ColorInput.parse(hex_color)

            # Find closest named color
            closest_named = self._find_closest_named_color(hex_color)

            # Log AI decision
            execution_time = (time.time() - start_time) * 1000
            await log_and_explain(
                module="color_parser",
                input_data={"text": color_str},
                features=features,
                output=result.data,
                decision=hex_color,
                confidence=0.85,
                reasoning=f"AI interpreted as {hex_color} ({closest_named or 'custom'})",
                execution_time_ms=execution_time,
            )

            return EnhancedColorInput.from_color_input(
                basic_color,
                interpretation=f"AI zinterpretowało '{color_str}' jako {hex_color}",
                confidence=0.85,
                closest_named=closest_named,
            )

        except Exception as e:
            # Log failed parsing
            execution_time = (time.time() - start_time) * 1000
            await log_and_explain(
                module="color_parser",
                input_data={"text": color_str},
                features=features,
                output=str(e),
                decision=None,
                confidence=0.0,
                reasoning=f"Parsing failed: {str(e)}",
                execution_time_ms=execution_time,
            )
            raise ValueError(f"AI color parsing failed: {str(e)}")

    def _find_closest_named_color(self, hex_color: str) -> Optional[str]:
        """Find the closest named color to a hex value."""
        target_rgb = self._hex_to_rgb(hex_color)

        min_distance = float("inf")
        closest_name = None

        for name, hex_val in self.NAMED_COLORS.items():
            rgb = self._hex_to_rgb(hex_val)
            distance = sum((a - b) ** 2 for a, b in zip(target_rgb, rgb))

            if distance < min_distance:
                min_distance = distance
                closest_name = name

        # Only return if reasonably close
        if min_distance < 10000:  # Threshold for "close enough"
            return closest_name
        return None

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_clean = hex_color.strip("#")
        return tuple(int(hex_clean[i : i + 2], 16) for i in (0, 2, 4))


# Convenience function for quick parsing
async def parse_color(color_str: str, use_ai: bool = True) -> EnhancedColorInput:
    """Quick color parsing function."""
    parser = ColorParser(use_ai=use_ai)
    return await parser.parse(color_str)
