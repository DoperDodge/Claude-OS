"""
Claude-OS User Onboarding Flow

First-boot experience that guides users through initial setup.
Runs once on first boot (or after factory reset).

Steps:
    1. Language & region selection
    2. WiFi setup
    3. Anthropic API key configuration
    4. Accessibility preferences
    5. Privacy & permissions review
    6. Create user profile
    7. Welcome chat with Claude

After onboarding, the system transitions to the normal launcher.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from enum import IntEnum, auto
from pathlib import Path

logger = logging.getLogger("onboarding")

CONFIG_DIR = Path(os.environ.get("CLAUDE_OS_CONFIG", "/etc/claude-os"))
ONBOARDING_COMPLETE = CONFIG_DIR / "onboarding-complete"


class OnboardingStep(IntEnum):
    """Steps in the onboarding flow."""
    WELCOME = 0
    LANGUAGE = 1
    WIFI = 2
    API_KEY = 3
    ACCESSIBILITY = 4
    PRIVACY = 5
    PROFILE = 6
    COMPLETE = 7


@dataclass
class OnboardingState:
    """Tracks the user's progress through onboarding."""
    current_step: OnboardingStep = OnboardingStep.WELCOME
    completed_steps: list[int] = field(default_factory=list)

    # Collected user choices
    language: str = "en"
    region: str = "US"
    timezone: str = "UTC"
    wifi_configured: bool = False
    api_key_set: bool = False
    accessibility_reviewed: bool = False
    privacy_reviewed: bool = False
    user_name: str = ""

    def to_dict(self) -> dict:
        return {
            "current_step": self.current_step.name.lower(),
            "step_number": int(self.current_step),
            "total_steps": int(OnboardingStep.COMPLETE),
            "completed": list(self.completed_steps),
            "choices": {
                "language": self.language,
                "region": self.region,
                "timezone": self.timezone,
                "wifi_configured": self.wifi_configured,
                "api_key_set": self.api_key_set,
                "user_name": self.user_name,
            },
        }


class OnboardingManager:
    """
    Manages the first-boot onboarding experience.

    The onboarding is conversational — Claude guides the user through
    setup via the chat interface rather than a traditional wizard UI.
    """

    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.state = OnboardingState()

    @staticmethod
    def is_onboarding_needed() -> bool:
        """Check if onboarding has been completed."""
        return not ONBOARDING_COMPLETE.exists()

    def get_state(self) -> dict:
        """Get current onboarding state."""
        return self.state.to_dict()

    # --- Step Handlers ---

    async def start(self) -> dict:
        """Start the onboarding flow. Returns the welcome message."""
        self.state.current_step = OnboardingStep.WELCOME

        return {
            "step": "welcome",
            "message": (
                "Welcome to Claude-OS! I'm Claude, and I'll be your guide "
                "through setting up your device. This will only take a "
                "few minutes.\n\n"
                "I'll help you with:\n"
                "- Choosing your language\n"
                "- Connecting to WiFi\n"
                "- Setting up your Claude account\n"
                "- Reviewing privacy settings\n\n"
                "Ready to get started?"
            ),
            "actions": [
                {"label": "Let's go!", "action": "next"},
                {"label": "Skip setup", "action": "skip"},
            ],
        }

    async def step_language(self, language: str = "en",
                            region: str = "US",
                            timezone: str = "UTC") -> dict:
        """Step 1: Set language and region."""
        self.state.language = language
        self.state.region = region
        self.state.timezone = timezone
        self.state.current_step = OnboardingStep.LANGUAGE
        self.state.completed_steps.append(int(OnboardingStep.LANGUAGE))

        # Apply locale settings
        self._apply_locale(language, region, timezone)

        return {
            "step": "language",
            "status": "complete",
            "message": f"Language set to {language}-{region}, timezone {timezone}.",
            "next_step": "wifi",
        }

    async def step_wifi(self, ssid: str = None, password: str = None) -> dict:
        """Step 2: Connect to WiFi."""
        self.state.current_step = OnboardingStep.WIFI

        if ssid:
            # Try to connect
            try:
                import sys
                sys.path.insert(0, os.path.join(
                    os.path.dirname(__file__), "../../system/bridge"
                ))
                from client import BridgeClient
                client = BridgeClient()
                result = client.wifi_connect(ssid, password)
                self.state.wifi_configured = result.get("connected", False)
            except Exception as e:
                return {
                    "step": "wifi",
                    "status": "error",
                    "message": f"Could not connect to {ssid}: {e}",
                    "retry": True,
                }

        self.state.completed_steps.append(int(OnboardingStep.WIFI))

        return {
            "step": "wifi",
            "status": "complete",
            "connected": self.state.wifi_configured,
            "next_step": "api_key",
        }

    async def step_api_key(self, api_key: str) -> dict:
        """Step 3: Configure Anthropic API key."""
        self.state.current_step = OnboardingStep.API_KEY

        if not api_key or not api_key.startswith("sk-"):
            return {
                "step": "api_key",
                "status": "error",
                "message": "Please enter a valid Anthropic API key (starts with 'sk-').",
            }

        # Save API key securely
        key_path = CONFIG_DIR / "api_key"
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            key_path.write_text(api_key.strip())
            os.chmod(key_path, 0o600)
            self.state.api_key_set = True
        except OSError as e:
            return {
                "step": "api_key",
                "status": "error",
                "message": f"Could not save API key: {e}",
            }

        self.state.completed_steps.append(int(OnboardingStep.API_KEY))

        return {
            "step": "api_key",
            "status": "complete",
            "message": "API key saved securely.",
            "next_step": "accessibility",
        }

    async def step_accessibility(self, settings: dict = None) -> dict:
        """Step 4: Review accessibility options."""
        self.state.current_step = OnboardingStep.ACCESSIBILITY
        self.state.accessibility_reviewed = True
        self.state.completed_steps.append(int(OnboardingStep.ACCESSIBILITY))

        # Apply any accessibility settings provided
        if settings:
            try:
                from accessibility import AccessibilityManager
                a11y = AccessibilityManager()
                await a11y.update_settings(settings)
            except ImportError:
                pass

        return {
            "step": "accessibility",
            "status": "complete",
            "message": (
                "Accessibility settings saved. You can always change "
                "these later by saying 'Hey Claude, open accessibility settings'."
            ),
            "next_step": "privacy",
        }

    async def step_privacy(self, permissions: dict = None) -> dict:
        """Step 5: Review privacy and permissions."""
        self.state.current_step = OnboardingStep.PRIVACY
        self.state.privacy_reviewed = True
        self.state.completed_steps.append(int(OnboardingStep.PRIVACY))

        # Apply permission choices
        if permissions:
            try:
                import sys
                sys.path.insert(0, os.path.join(
                    os.path.dirname(__file__), "../../system/bridge"
                ))
                from permissions import PermissionManager
                pm = PermissionManager(CONFIG_DIR / "permissions.json")
                pm.load()
                for perm, granted in permissions.items():
                    if granted:
                        pm.grant(perm)
                    else:
                        pm.revoke(perm)
            except ImportError:
                pass

        return {
            "step": "privacy",
            "status": "complete",
            "message": (
                "Privacy settings saved. Claude will always ask before "
                "accessing sensitive data. You're in control."
            ),
            "next_step": "profile",
        }

    async def step_profile(self, name: str = "") -> dict:
        """Step 6: Create user profile."""
        self.state.current_step = OnboardingStep.PROFILE
        self.state.user_name = name
        self.state.completed_steps.append(int(OnboardingStep.PROFILE))

        # Save user profile
        profile = {
            "name": name,
            "language": self.state.language,
            "region": self.state.region,
            "timezone": self.state.timezone,
            "created_at": __import__("time").time(),
        }

        profile_path = CONFIG_DIR / "user-profile.json"
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            profile_path.write_text(json.dumps(profile, indent=2))
        except OSError:
            pass

        return {
            "step": "profile",
            "status": "complete",
            "next_step": "complete",
        }

    async def complete(self) -> dict:
        """Mark onboarding as complete."""
        self.state.current_step = OnboardingStep.COMPLETE

        # Write completion marker
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            ONBOARDING_COMPLETE.write_text(
                json.dumps({
                    "completed_at": __import__("time").time(),
                    "steps_completed": self.state.completed_steps,
                })
            )
        except OSError:
            pass

        if self.event_bus:
            await self.event_bus.emit("onboarding.complete", {
                "user_name": self.state.user_name,
            })

        logger.info("Onboarding complete for user: %s", self.state.user_name)

        greeting = f"Hi {self.state.user_name}! " if self.state.user_name else ""

        return {
            "step": "complete",
            "status": "complete",
            "message": (
                f"{greeting}Your device is all set up! "
                "I'm Claude, and I'm here whenever you need me. "
                "Just type or say 'Hey Claude' to get started.\n\n"
                "Try asking me to:\n"
                "- Check your WiFi connection\n"
                "- Tell you about the weather\n"
                "- Set a reminder\n"
                "- Help you with anything on your mind"
            ),
        }

    async def skip(self) -> dict:
        """Skip onboarding entirely."""
        await self.complete()
        return {
            "step": "complete",
            "status": "skipped",
            "message": (
                "Setup skipped. You can always configure your device "
                "later through settings. Just say 'Hey Claude, open settings'."
            ),
        }

    # --- Internal ---

    def _apply_locale(self, language: str, region: str, timezone: str):
        """Apply locale and timezone settings to the system."""
        # Set timezone
        tz_path = f"/usr/share/zoneinfo/{timezone}"
        if os.path.exists(tz_path):
            try:
                localtime = Path("/etc/localtime")
                if localtime.exists() or localtime.is_symlink():
                    localtime.unlink()
                localtime.symlink_to(tz_path)
            except OSError:
                pass

        # Set locale
        try:
            locale_conf = Path("/etc/locale.conf")
            locale_str = f"{language}_{region}.UTF-8"
            locale_conf.write_text(f"LANG={locale_str}\n")
        except OSError:
            pass
