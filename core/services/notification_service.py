"""Notification service for sending specific types of Discord notifications."""

from typing import Any

import discord

from core.interfaces.messaging_interfaces import (
    IEmbedBuilder,
    IMessageSender,
    INotificationService,
)
from core.services.base_service import BaseService


class NotificationService(BaseService, INotificationService):
    """Service for sending specialized notifications to Discord."""

    def __init__(
        self, embed_builder: IEmbedBuilder, message_sender: IMessageSender, **kwargs
    ):
        super().__init__(**kwargs)
        self.embed_builder = embed_builder
        self.message_sender = message_sender

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate notification operation."""
        return True

    async def send_permission_update(
        self, ctx: Any, target: discord.Member, permission: str, new_value: bool
    ) -> None:
        """Send permission update notification."""
        try:
            action = "przyznano" if new_value else "odebrano"
            embed = self.embed_builder.create_success_embed(
                title="Uprawnienie zaktualizowane",
                description=f"Użytkownikowi {target.mention} {action} uprawnienie: **{permission}**",
            )

            await self.message_sender.send_to_context(ctx, embed=embed)

            self._log_operation(
                "send_permission_update",
                target_id=target.id,
                permission=permission,
                new_value=new_value,
            )

        except Exception as e:
            self._log_error(
                "send_permission_update",
                e,
                target_id=target.id,
                permission=permission,
            )

    async def send_user_not_found(self, ctx: Any) -> None:
        """Send user not found notification."""
        try:
            embed = self.embed_builder.create_error_embed(
                title="Użytkownik nie znaleziony",
                description="Nie można znaleźć określonego użytkownika na serwerze.",
            )

            await self.message_sender.send_to_context(ctx, embed=embed)
            self._log_operation("send_user_not_found")

        except Exception as e:
            self._log_error("send_user_not_found", e)

    async def send_no_permission(self, ctx: Any, required_permission: str) -> None:
        """Send no permission notification."""
        try:
            embed = self.embed_builder.create_error_embed(
                title="Brak uprawnień",
                description=f"Nie masz wystarczających uprawnień do wykonania tej akcji.\n"
                f"Wymagane uprawnienie: **{required_permission}**",
            )

            await self.message_sender.send_to_context(ctx, embed=embed)

            self._log_operation(
                "send_no_permission",
                required_permission=required_permission,
                user_id=getattr(
                    ctx.author if hasattr(ctx, "author") else ctx.user, "id", None
                ),
            )

        except Exception as e:
            self._log_error(
                "send_no_permission", e, required_permission=required_permission
            )

    async def send_voice_channel_info(
        self, ctx: Any, channel: discord.VoiceChannel, **info: Any
    ) -> None:
        """Send voice channel information."""
        try:
            embed = self.embed_builder.create_voice_info_embed(channel, **info)
            await self.message_sender.send_to_context(ctx, embed=embed)

            self._log_operation(
                "send_voice_channel_info",
                channel_id=channel.id,
                info_fields=list(info.keys()),
            )

        except Exception as e:
            self._log_error("send_voice_channel_info", e, channel_id=channel.id)

    async def send_role_update(
        self, ctx: Any, target: discord.Member, role: discord.Role, added: bool
    ) -> None:
        """Send role update notification."""
        try:
            action = "przyznano" if added else "odebrano"
            embed = self.embed_builder.create_success_embed(
                title="Rola zaktualizowana",
                description=f"Użytkownikowi {target.mention} {action} rolę {role.mention}",
            )

            await self.message_sender.send_to_context(ctx, embed=embed)

            self._log_operation(
                "send_role_update",
                target_id=target.id,
                role_id=role.id,
                added=added,
            )

        except Exception as e:
            self._log_error(
                "send_role_update",
                e,
                target_id=target.id,
                role_id=role.id,
            )

    async def send_voice_not_connected(
        self, ctx: Any, target: discord.Member = None
    ) -> None:
        """Send notification that user is not connected to voice channel."""
        try:
            if target:
                description = f"Użytkownik {target.mention} nie jest połączony z żadnym kanałem głosowym."
            else:
                description = "Nie jesteś połączony z żadnym kanałem głosowym."

            embed = self.embed_builder.create_error_embed(
                title="Brak połączenia z kanałem głosowym",
                description=description,
            )

            await self.message_sender.send_to_context(ctx, embed=embed)

            self._log_operation(
                "send_voice_not_connected",
                target_id=target.id if target else None,
            )

        except Exception as e:
            self._log_error("send_voice_not_connected", e)

    async def send_premium_required(self, ctx: Any, feature: str) -> None:
        """Send premium required notification."""
        try:
            embed = self.embed_builder.create_warning_embed(
                title="Funkcja Premium",
                description=f"Funkcja **{feature}** jest dostępna tylko dla użytkowników Premium.\n"
                "Sprawdź dostępne opcje Premium w sklepie bota.",
            )

            await self.message_sender.send_to_context(ctx, embed=embed)

            self._log_operation(
                "send_premium_required",
                feature=feature,
                user_id=getattr(
                    ctx.author if hasattr(ctx, "author") else ctx.user, "id", None
                ),
            )

        except Exception as e:
            self._log_error("send_premium_required", e, feature=feature)

    async def send_operation_success(
        self, ctx: Any, operation: str, details: str = None
    ) -> None:
        """Send generic operation success notification."""
        try:
            description = f"Operacja **{operation}** została wykonana pomyślnie."
            if details:
                description += f"\n\n{details}"

            embed = self.embed_builder.create_success_embed(
                title="Operacja zakończona sukcesem",
                description=description,
            )

            await self.message_sender.send_to_context(ctx, embed=embed)
            self._log_operation("send_operation_success", operation=operation)

        except Exception as e:
            self._log_error("send_operation_success", e, operation=operation)

    async def send_operation_error(
        self, ctx: Any, operation: str, error_details: str = None
    ) -> None:
        """Send generic operation error notification."""
        try:
            description = f"Operacja **{operation}** nie powiodła się."
            if error_details:
                description += f"\n\n**Szczegóły:** {error_details}"

            embed = self.embed_builder.create_error_embed(
                title="Błąd operacji",
                description=description,
            )

            await self.message_sender.send_to_context(ctx, embed=embed)
            self._log_operation("send_operation_error", operation=operation)

        except Exception as e:
            self._log_error("send_operation_error", e, operation=operation)
