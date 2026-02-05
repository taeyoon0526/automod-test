import asyncio
import random
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import discord
from redbot.core import commands, Config

OWNER_USER_ID = 1448530688558235719
RULE_NAME_PREFIX = "[AMSEED]"
DEFAULT_CREATE_COUNT = 10

ACTION_BLOCK_MESSAGE = 1
ACTION_SEND_ALERT = 2

TRIGGER_TYPE_KEYWORD = 1
EVENT_TYPE_MESSAGE_SEND = 1

CREATE_SLEEP_MIN = 0.35
CREATE_SLEEP_MAX = 0.9
BATCH_SLEEP_EVERY = 5
BATCH_SLEEP_SECONDS = 1.5

CUSTOM_MESSAGE = (
    "AutoMod seed rule (badge test). If this blocks unexpectedly, delete the rule."
)


class AutoModSeeder(commands.Cog):
    """Seed a guild with random AutoMod rules for badge testing."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=8237451234, force_registration=True)
        self.config.register_guild(
            owner_user_id=OWNER_USER_ID,
            seeded_rule_ids=[],
            last_run_ts=0,
            default_count=DEFAULT_CREATE_COUNT,
            default_enabled=False,
            logging_enabled=False,
            log_channel_id=None,
            allow_alert_mode=False,
            action_mode="block",
            silent_denied=False,
        )

    # ---------------------
    # Utility helpers
    # ---------------------
    def _random_keyword(self, guild_id: int) -> str:
        token = secrets.token_hex(6)
        return f"amseed_{guild_id}_{token}"

    def _random_keywords(self, guild_id: int) -> List[str]:
        return [self._random_keyword(guild_id) for _ in range(random.randint(1, 3))]

    def _has_manage_guild(self, guild: discord.Guild) -> bool:
        me = guild.me or guild.get_member(self.bot.user.id)
        return bool(me and me.guild_permissions.manage_guild)

    async def _should_silent_deny(self, guild: discord.Guild) -> bool:
        return await self.config.guild(guild).silent_denied()

    async def _is_owner(self, ctx: commands.Context) -> bool:
        if ctx.author.id == OWNER_USER_ID:
            return True
        if ctx.guild and await self._should_silent_deny(ctx.guild):
            return False
        await ctx.send("권한 없음")
        return False

    def _parse_bool(self, value: Optional[str]) -> Optional[bool]:
        if value is None:
            return None
        lowered = value.lower()
        if lowered in {"true", "t", "yes", "y", "on", "1"}:
            return True
        if lowered in {"false", "f", "no", "n", "off", "0"}:
            return False
        raise commands.BadArgument("enabled는 true/false/yes/no/on/off/1/0 중 하나여야 합니다.")

    async def _sleep_with_backoff(self, attempt: int) -> None:
        if attempt <= 0:
            return
        await asyncio.sleep(1.5)

    def _build_trigger_metadata(self, keywords: List[str]) -> Dict[str, Any]:
        return {"keyword_filter": keywords}

    def _build_actions_payload(
        self, action_mode: str, channel_id: Optional[int]
    ) -> List[Dict[str, Any]]:
        action_type = ACTION_BLOCK_MESSAGE if action_mode == "block" else ACTION_SEND_ALERT
        payload = {"type": action_type, "metadata": {}}
        if action_type == ACTION_BLOCK_MESSAGE:
            payload["metadata"]["custom_message"] = CUSTOM_MESSAGE
        elif channel_id:
            payload["metadata"]["channel_id"] = str(channel_id)
        return [payload]

    def _summarize_rule(self, rule: discord.AutoModRule) -> str:
        state = "enabled" if rule.enabled else "disabled"
        return f"{rule.name} (ID: {rule.id}, {state})"

    async def _maybe_log(
        self,
        guild: discord.Guild,
        action: str,
        requested: int,
        success: int,
        failed: int,
        note: str,
    ) -> None:
        if not await self.config.guild(guild).logging_enabled():
            return
        channel_id = await self.config.guild(guild).log_channel_id()
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if not channel:
            return
        embed = discord.Embed(title="AutoModSeeder")
        embed.add_field(name="Action", value=action, inline=True)
        embed.add_field(name="Count", value=str(requested), inline=True)
        embed.add_field(name="Success", value=str(success), inline=True)
        embed.add_field(name="Fail", value=str(failed), inline=True)
        embed.add_field(name="Note", value=note or "-", inline=False)
        await channel.send(embed=embed)

    async def _fetch_rules(self, guild: discord.Guild) -> List[discord.AutoModRule]:
        if hasattr(guild, "fetch_automod_rules"):
            return await guild.fetch_automod_rules()
        return await self._rest_fetch_rules(guild)

    async def _fetch_rule_map(self, guild: discord.Guild) -> Dict[int, discord.AutoModRule]:
        rules = await self._fetch_rules(guild)
        return {rule.id: rule for rule in rules}

    async def _rest_fetch_rules(self, guild: discord.Guild) -> List[discord.AutoModRule]:
        route = discord.http.Route("GET", "/guilds/{guild_id}/auto-moderation/rules", guild_id=guild.id)
        data = await self.bot.http.request(route)
        return [discord.AutoModRule(data=rule, guild=guild, state=guild._state) for rule in data]

    async def _rest_create_rule(self, guild: discord.Guild, payload: Dict[str, Any]) -> discord.AutoModRule:
        route = discord.http.Route("POST", "/guilds/{guild_id}/auto-moderation/rules", guild_id=guild.id)
        data = await self.bot.http.request(route, json=payload)
        return discord.AutoModRule(data=data, guild=guild, state=guild._state)

    async def _rest_delete_rule(self, guild: discord.Guild, rule_id: int) -> None:
        route = discord.http.Route(
            "DELETE",
            "/guilds/{guild_id}/auto-moderation/rules/{rule_id}",
            guild_id=guild.id,
            rule_id=rule_id,
        )
        await self.bot.http.request(route)

    async def _create_rule(
        self,
        guild: discord.Guild,
        name: str,
        keywords: List[str],
        enabled: bool,
        action_mode: str,
        channel_id: Optional[int],
    ) -> discord.AutoModRule:
        if (
            hasattr(guild, "create_automod_rule")
            and hasattr(discord, "AutoModRuleTriggerMetadata")
            and hasattr(discord, "AutoModRuleAction")
        ):
            trigger_metadata = discord.AutoModRuleTriggerMetadata(keyword_filter=keywords)
            if action_mode == "alert" and channel_id:
                action = discord.AutoModRuleAction(
                    discord.AutoModActionType.send_alert_message,
                    channel_id=channel_id,
                )
            else:
                action = discord.AutoModRuleAction(
                    discord.AutoModActionType.block_message,
                    custom_message=CUSTOM_MESSAGE,
                )
            return await guild.create_automod_rule(
                name=name,
                event_type=discord.AutoModEventType.message_send,
                trigger_type=discord.AutoModRuleTriggerType.keyword,
                trigger_metadata=trigger_metadata,
                actions=[action],
                enabled=enabled,
            )

        payload = {
            "name": name,
            "event_type": EVENT_TYPE_MESSAGE_SEND,
            "trigger_type": TRIGGER_TYPE_KEYWORD,
            "trigger_metadata": self._build_trigger_metadata(keywords),
            "actions": self._build_actions_payload(action_mode, channel_id),
            "enabled": enabled,
        }
        return await self._rest_create_rule(guild, payload)

    async def _delete_rule(self, guild: discord.Guild, rule: discord.AutoModRule) -> None:
        if hasattr(rule, "delete"):
            await rule.delete()
            return
        await self._rest_delete_rule(guild, rule.id)

    async def _enable_rule(self, guild: discord.Guild, rule: discord.AutoModRule) -> discord.AutoModRule:
        if hasattr(rule, "edit"):
            return await rule.edit(enabled=True)
        route = discord.http.Route(
            "PATCH",
            "/guilds/{guild_id}/auto-moderation/rules/{rule_id}",
            guild_id=guild.id,
            rule_id=rule.id,
        )
        payload = {"enabled": True}
        data = await self.bot.http.request(route, json=payload)
        return discord.AutoModRule(data=data, guild=guild, state=guild._state)

    async def _sync_seeded_ids(
        self, guild: discord.Guild
    ) -> Tuple[List[int], Dict[int, discord.AutoModRule]]:
        rule_map = await self._fetch_rule_map(guild)
        stored = await self.config.guild(guild).seeded_rule_ids()
        filtered = [rule_id for rule_id in stored if rule_id in rule_map]
        if filtered != stored:
            await self.config.guild(guild).seeded_rule_ids.set(filtered)
        return filtered, rule_map

    async def _attempt_create(
        self,
        guild: discord.Guild,
        enabled: bool,
        action_mode: str,
        channel_id: Optional[int],
    ) -> Tuple[Optional[discord.AutoModRule], Optional[str], Optional[int]]:
        name = f"{RULE_NAME_PREFIX} seed {secrets.token_hex(4)}"
        keywords = self._random_keywords(guild.id)
        try:
            rule = await self._create_rule(guild, name, keywords, enabled, action_mode, channel_id)
            return rule, None, None
        except discord.Forbidden:
            return None, "forbidden", None
        except discord.HTTPException as exc:
            status = getattr(exc, "status", None)
            return None, "http", status

    async def _create_seed_rules(
        self,
        ctx: commands.Context,
        count: int,
        enabled: bool,
    ) -> None:
        guild = ctx.guild
        if not self._has_manage_guild(guild):
            await ctx.send("봇에 서버 관리(Manage Guild) 권한이 필요합니다.")
            return

        stored_ids, rule_map = await self._sync_seeded_ids(guild)
        action_mode = await self.config.guild(guild).action_mode()
        allow_alert = await self.config.guild(guild).allow_alert_mode()
        channel_id = await self.config.guild(guild).log_channel_id()
        if action_mode == "alert" and not allow_alert:
            action_mode = "block"
        if action_mode == "alert" and not channel_id:
            action_mode = "block"
            note = "alert 모드 로그 채널이 없어 block으로 대체됨"
        else:
            note = ""

        requested = count
        created: List[discord.AutoModRule] = []
        failed = 0
        stopped_by_limit = False

        for idx in range(requested):
            await asyncio.sleep(random.uniform(CREATE_SLEEP_MIN, CREATE_SLEEP_MAX))
            if idx > 0 and idx % BATCH_SLEEP_EVERY == 0:
                await asyncio.sleep(BATCH_SLEEP_SECONDS)

            rule, err, status = await self._attempt_create(
                guild, enabled, action_mode, channel_id
            )
            if rule:
                created.append(rule)
                continue

            if err == "forbidden":
                failed += 1
                note = "권한 부족으로 중단됨"
                stopped_by_limit = True
                break

            if err == "http":
                failed += 1
                if status == 429:
                    await self._sleep_with_backoff(1)
                    rule, err, status = await self._attempt_create(
                        guild, enabled, action_mode, channel_id
                    )
                    if rule:
                        created.append(rule)
                        continue
                    failed += 1
                    note = "레이트리밋(429)으로 중단됨"
                    stopped_by_limit = True
                    break
                if status == 400:
                    note = "서버 AutoMod 제한 또는 파라미터 오류 가능"
                    stopped_by_limit = True
                    break
                if status in {403, 404}:
                    note = "권한 또는 대상 오류로 중단됨"
                    stopped_by_limit = True
                    break

            failed += 1

        if created:
            new_ids = [rule.id for rule in created]
            await self.config.guild(guild).seeded_rule_ids.set(stored_ids + new_ids)

        await self.config.guild(guild).last_run_ts.set(int(time.time()))

        success = len(created)
        remaining = requested - success - failed
        failed += max(0, remaining)

        summary_lines = [
            f"요청: {requested}",
            f"성공: {success}",
            f"실패: {failed}",
        ]
        if stopped_by_limit:
            summary_lines.append("서버의 AutoMod 제한 때문에 10개를 전부 만들지 못할 수 있습니다.")
        if created:
            display = [self._summarize_rule(rule) for rule in created[:5]]
            if len(created) > 5:
                display.append(f"외 {len(created) - 5}개")
            summary_lines.append("생성됨: " + " | ".join(display))

        await ctx.send("\n".join(summary_lines))
        await self._maybe_log(
            guild,
            action="create",
            requested=requested,
            success=success,
            failed=failed,
            note=note,
        )

    # ---------------------
    # Commands
    # ---------------------
    @commands.group(name="automodseed", aliases=["amseed"], invoke_without_command=True)
    @commands.guild_only()
    async def automodseed(self, ctx: commands.Context) -> None:
        """Create random AutoMod rules for badge testing."""
        if not await self._is_owner(ctx):
            return
        default_count = await self.config.guild(ctx.guild).default_count()
        default_enabled = await self.config.guild(ctx.guild).default_enabled()
        await self._create_seed_rules(ctx, default_count, default_enabled)

    @automodseed.command(name="create")
    async def automodseed_create(
        self, ctx: commands.Context, count: Optional[int] = None, enabled: Optional[str] = None
    ) -> None:
        """Create AutoMod seed rules."""
        if not await self._is_owner(ctx):
            return
        if count is None:
            count = await self.config.guild(ctx.guild).default_count()
        count = max(1, min(10, int(count)))
        enabled_value = self._parse_bool(enabled)
        if enabled_value is None:
            enabled_value = await self.config.guild(ctx.guild).default_enabled()
        await self._create_seed_rules(ctx, count, enabled_value)

    @automodseed.command(name="list")
    async def automodseed_list(self, ctx: commands.Context) -> None:
        """List AutoMod rules created by this cog."""
        if not await self._is_owner(ctx):
            return
        stored_ids, rule_map = await self._sync_seeded_ids(ctx.guild)
        if not stored_ids:
            await ctx.send("이 Cog가 만든 규칙이 없습니다.")
            return
        lines = []
        for rule_id in stored_ids:
            rule = rule_map.get(rule_id)
            if not rule:
                continue
            lines.append(self._summarize_rule(rule))
        await ctx.send("\n".join(lines[:20]))

    @automodseed.command(name="status")
    async def automodseed_status(self, ctx: commands.Context) -> None:
        """Show status for seed rules."""
        if not await self._is_owner(ctx):
            return
        stored_ids, rule_map = await self._sync_seeded_ids(ctx.guild)
        actual_count = len([rule_id for rule_id in stored_ids if rule_id in rule_map])
        last_run = await self.config.guild(ctx.guild).last_run_ts()
        last_run_text = "-"
        if last_run:
            dt = datetime.fromtimestamp(last_run, tz=timezone.utc)
            last_run_text = discord.utils.format_dt(dt, "R")
        lines = [
            f"Config 저장 수: {len(stored_ids)}",
            f"실제 존재 수: {actual_count}",
            f"최근 실행: {last_run_text}",
        ]
        await ctx.send("\n".join(lines))

    @automodseed.command(name="purge")
    async def automodseed_purge(self, ctx: commands.Context) -> None:
        """Delete AutoMod rules created by this cog."""
        if not await self._is_owner(ctx):
            return
        if not self._has_manage_guild(ctx.guild):
            await ctx.send("봇에 서버 관리(Manage Guild) 권한이 필요합니다.")
            return
        stored_ids, rule_map = await self._sync_seeded_ids(ctx.guild)
        if not stored_ids:
            await ctx.send("삭제할 규칙이 없습니다.")
            return

        success = 0
        failed = 0
        note = ""

        for idx, rule_id in enumerate(list(stored_ids)):
            await asyncio.sleep(random.uniform(CREATE_SLEEP_MIN, CREATE_SLEEP_MAX))
            if idx > 0 and idx % BATCH_SLEEP_EVERY == 0:
                await asyncio.sleep(BATCH_SLEEP_SECONDS)

            rule = rule_map.get(rule_id)
            if not rule:
                stored_ids.remove(rule_id)
                continue
            try:
                await self._delete_rule(ctx.guild, rule)
                success += 1
                stored_ids.remove(rule_id)
            except discord.Forbidden:
                failed += 1
                note = "권한 부족"
                break
            except discord.HTTPException as exc:
                status = getattr(exc, "status", None)
                if status == 429:
                    await self._sleep_with_backoff(1)
                    try:
                        await self._delete_rule(ctx.guild, rule)
                        success += 1
                        stored_ids.remove(rule_id)
                        continue
                    except discord.HTTPException:
                        failed += 1
                        note = "레이트리밋"
                        break
                failed += 1

        await self.config.guild(ctx.guild).seeded_rule_ids.set(stored_ids)
        summary = f"삭제 성공: {success}, 실패: {failed}"
        if note:
            summary += f" ({note})"
        await ctx.send(summary)
        await self._maybe_log(
            ctx.guild,
            action="purge",
            requested=success + failed,
            success=success,
            failed=failed,
            note=note,
        )

    @automodseed.command(name="enableall")
    async def automodseed_enableall(self, ctx: commands.Context) -> None:
        """Enable all AutoMod rules created by this cog."""
        if not await self._is_owner(ctx):
            return
        if not self._has_manage_guild(ctx.guild):
            await ctx.send("봇에 서버 관리(Manage Guild) 권한이 필요합니다.")
            return
        stored_ids, rule_map = await self._sync_seeded_ids(ctx.guild)
        if not stored_ids:
            await ctx.send("활성화할 규칙이 없습니다.")
            return

        success = 0
        failed = 0
        note = ""

        for idx, rule_id in enumerate(list(stored_ids)):
            await asyncio.sleep(random.uniform(CREATE_SLEEP_MIN, CREATE_SLEEP_MAX))
            if idx > 0 and idx % BATCH_SLEEP_EVERY == 0:
                await asyncio.sleep(BATCH_SLEEP_SECONDS)

            rule = rule_map.get(rule_id)
            if not rule:
                stored_ids.remove(rule_id)
                continue
            try:
                await self._enable_rule(ctx.guild, rule)
                success += 1
            except discord.Forbidden:
                failed += 1
                note = "권한 부족"
                break
            except discord.HTTPException as exc:
                status = getattr(exc, "status", None)
                if status == 429:
                    await self._sleep_with_backoff(1)
                    try:
                        await self._enable_rule(ctx.guild, rule)
                        success += 1
                        continue
                    except discord.HTTPException:
                        failed += 1
                        note = "레이트리밋"
                        break
                failed += 1

        summary = f"활성화 성공: {success}, 실패: {failed}"
        if note:
            summary += f" ({note})"
        await ctx.send(summary)
        await self._maybe_log(
            ctx.guild,
            action="enableall",
            requested=success + failed,
            success=success,
            failed=failed,
            note=note,
        )

    @automodseed.group(name="set")
    async def automodseed_set(self, ctx: commands.Context) -> None:
        """Optional settings for AutoModSeeder."""
        if not await self._is_owner(ctx):
            return

    @automodseed_set.command(name="mode")
    async def automodseed_set_mode(self, ctx: commands.Context, mode: str) -> None:
        """Set action mode (block or alert)."""
        if not await self._is_owner(ctx):
            return
        mode = mode.lower()
        if mode not in {"block", "alert"}:
            await ctx.send("mode는 block 또는 alert만 가능합니다.")
            return
        allow = await self.config.guild(ctx.guild).allow_alert_mode()
        if mode == "alert" and not allow:
            await ctx.send("alert 모드는 잠겨 있습니다.")
            return
        await self.config.guild(ctx.guild).action_mode.set(mode)
        await ctx.send(f"action_mode = {mode}")

    @automodseed_set.command(name="lockdenied")
    async def automodseed_set_lockdenied(self, ctx: commands.Context, value: Optional[str] = None) -> None:
        """Toggle silent deny for non-owner users."""
        if not await self._is_owner(ctx):
            return
        silent = self._parse_bool(value)
        if silent is None:
            silent = not await self.config.guild(ctx.guild).silent_denied()
        await self.config.guild(ctx.guild).silent_denied.set(silent)
        await ctx.send(f"silent_denied = {silent}")
