"""Message sender service for Discord communication."""

import logging
from typing import Optional

import discord
from discord.ext import commands

from core.interfaces.messaging_interfaces import IMessageSender
from core.services.base_service import BaseService


class MessageSenderService(BaseService, IMessageSender):
    """Service for sending messages to Discord channels and users."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate message sending operation."""
        return True

    async def send_embed(
        self,
        target: discord.abc.Messageable,
        embed: discord.Embed,
        allowed_mentions: Optional[discord.AllowedMentions] = None,
        ephemeral: bool = False,
    ) -> Optional[discord.Message]:
        """Send an embed to a Discord channel or user."""
        try:
            # Handle different target types
            if isinstance(target, discord.Interaction):
                if target.response.is_done():
                    message = await target.followup.send(
                        embed=embed,
                        ephemeral=ephemeral,
                        allowed_mentions=allowed_mentions,
                    )
                else:
                    await target.response.send_message(
                        embed=embed,
                        ephemeral=ephemeral,
                        allowed_mentions=allowed_mentions,
                    )
                    message = await target.original_response()

                self._log_operation(
                    "send_embed_interaction",
                    target_type="interaction",
                    user_id=target.user.id,
                    ephemeral=ephemeral,
                )
                return message

            elif hasattr(target, "send"):
                # Regular channel or user
                message = await target.send(embed=embed, allowed_mentions=allowed_mentions)

                self._log_operation(
                    "send_embed",
                    target_type=type(target).__name__,
                    target_id=getattr(target, "id", None),
                )
                return message

            else:
                self._log_error(
                    "send_embed",
                    ValueError(f"Unsupported target type: {type(target)}"),
                    target_type=type(target).__name__,
                )
                return None

        except discord.HTTPException as e:
            self._log_error(
                "send_embed",
                e,
                target_type=type(target).__name__,
                error_code=e.code if hasattr(e, "code") else None,
            )
            return None
        except Exception as e:
            self._log_error("send_embed", e, target_type=type(target).__name__)
            return None

    async def send_text(
        self,
        target: discord.abc.Messageable,
        content: str,
        allowed_mentions: Optional[discord.AllowedMentions] = None,
        ephemeral: bool = False,
    ) -> Optional[discord.Message]:
        """Send a text message to a Discord channel or user."""
        try:
            # Handle different target types
            if isinstance(target, discord.Interaction):
                if target.response.is_done():
                    message = await target.followup.send(
                        content=content,
                        ephemeral=ephemeral,
                        allowed_mentions=allowed_mentions,
                    )
                else:
                    await target.response.send_message(
                        content=content,
                        ephemeral=ephemeral,
                        allowed_mentions=allowed_mentions,
                    )
                    message = await target.original_response()

                self._log_operation(
                    "send_text_interaction",
                    target_type="interaction",
                    user_id=target.user.id,
                    ephemeral=ephemeral,
                    content_length=len(content),
                )
                return message

            elif hasattr(target, "send"):
                # Regular channel or user
                message = await target.send(content=content, allowed_mentions=allowed_mentions)

                self._log_operation(
                    "send_text",
                    target_type=type(target).__name__,
                    target_id=getattr(target, "id", None),
                    content_length=len(content),
                )
                return message

            else:
                self._log_error(
                    "send_text",
                    ValueError(f"Unsupported target type: {type(target)}"),
                    target_type=type(target).__name__,
                )
                return None

        except discord.HTTPException as e:
            self._log_error(
                "send_text",
                e,
                target_type=type(target).__name__,
                error_code=e.code if hasattr(e, "code") else None,
            )
            return None
        except Exception as e:
            self._log_error("send_text", e, target_type=type(target).__name__)
            return None

    async def reply_to_interaction(
        self,
        interaction: discord.Interaction,
        embed: Optional[discord.Embed] = None,
        content: Optional[str] = None,
        ephemeral: bool = False,
    ) -> None:
        """Reply to a Discord interaction."""
        try:
            kwargs = {"ephemeral": ephemeral}

            if embed:
                kwargs["embed"] = embed
            if content:
                kwargs["content"] = content

            if interaction.response.is_done():
                await interaction.followup.send(**kwargs)
                self._log_operation(
                    "followup_interaction",
                    user_id=interaction.user.id,
                    ephemeral=ephemeral,
                )
            else:
                await interaction.response.send_message(**kwargs)
                self._log_operation(
                    "respond_interaction",
                    user_id=interaction.user.id,
                    ephemeral=ephemeral,
                )

        except discord.HTTPException as e:
            self._log_error(
                "reply_to_interaction",
                e,
                user_id=interaction.user.id,
                error_code=e.code if hasattr(e, "code") else None,
            )
        except Exception as e:
            self._log_error("reply_to_interaction", e, user_id=interaction.user.id)

    async def send_to_context(
        self,
        ctx: commands.Context,
        embed: Optional[discord.Embed] = None,
        content: Optional[str] = None,
        allowed_mentions: Optional[discord.AllowedMentions] = None,
    ) -> Optional[discord.Message]:
        """Send message using command context (handles both slash and text commands)."""
        try:
            # Check if it's an interaction context
            if hasattr(ctx, "interaction") and ctx.interaction:
                await self.reply_to_interaction(ctx.interaction, embed=embed, content=content)
                return await ctx.interaction.original_response()

            # Regular text command context
            kwargs = {"allowed_mentions": allowed_mentions}
            if embed:
                kwargs["embed"] = embed
            if content:
                kwargs["content"] = content

            message = await ctx.send(**kwargs)

            self._log_operation(
                "send_to_context",
                context_type="text_command",
                channel_id=ctx.channel.id,
                author_id=ctx.author.id,
            )
            return message

        except discord.HTTPException as e:
            self._log_error(
                "send_to_context",
                e,
                context_type=type(ctx).__name__,
                error_code=e.code if hasattr(e, "code") else None,
            )
            return None
        except Exception as e:
            self._log_error("send_to_context", e, context_type=type(ctx).__name__)
            return None
