"""/configureaza-server: creează rolurile, categoriile și canalele din config/server.yaml.

Reguli de siguranță:
- nu șterge și nu redenumește nimic;
- canalele existente sunt recunoscute după nume (și categorie);
- cu simulare=True (implicit) doar arată ce ar face.
"""
from __future__ import annotations

import io

import discord
from discord import app_commands
from discord.ext import commands

from ..config import CategorySpec, ChannelSpec


def _color(hex_str: str | None) -> discord.Colour:
    if not hex_str:
        return discord.Colour.default()
    return discord.Colour(int(hex_str.lstrip("#"), 16))


def _norm(name: str) -> str:
    return name.lower().replace(" ", "").replace("|", "").replace("-", "")


class SetupServer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ------------------------------------------------------------------ roluri
    def _wanted_roles(self) -> list[dict]:
        cfg = self.bot.cfg
        roles = [{"name": cfg.staff_role, "color": cfg.staff_role_raw.get("culoare"), "hoist": cfg.staff_role_raw.get("separat", True)}]
        for r in cfg.extra_roles:
            roles.append({"name": r["nume"], "color": r.get("culoare"), "hoist": r.get("separat", False)})
        for g in cfg.games:
            roles.append({"name": g.role, "color": g.color, "hoist": False})
            if g.competitive_role:
                roles.append({"name": g.competitive_role, "color": None, "hoist": False})
        return roles

    # ------------------------------------------------------------ permisiuni
    def _category_overwrites(self, guild: discord.Guild, spec: CategorySpec, roles: dict[str, discord.Role]):
        cfg = self.bot.cfg
        staff = roles.get(cfg.staff_role)
        ow: dict = {guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, manage_threads=True)}
        if spec.access == "staff":
            ow[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
            if staff:
                ow[staff] = discord.PermissionOverwrite(view_channel=True)
        elif spec.access == "game" and cfg.hide_games:
            ow[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
            game_role = roles.get(spec.game_role or "")
            if game_role:
                ow[game_role] = discord.PermissionOverwrite(view_channel=True)
            if staff:
                ow[staff] = discord.PermissionOverwrite(view_channel=True)
        return ow

    def _channel_overwrites(self, guild, category: discord.CategoryChannel, spec: ChannelSpec, roles):
        ow = dict(category.overwrites)
        if spec.readonly:
            base = ow.get(guild.default_role, discord.PermissionOverwrite())
            base.update(send_messages=False, create_public_threads=False, add_reactions=True)
            ow[guild.default_role] = base
            staff = roles.get(self.bot.cfg.staff_role)
            if staff:
                s = ow.get(staff, discord.PermissionOverwrite())
                s.update(send_messages=True)
                ow[staff] = s
            me = ow.get(guild.me, discord.PermissionOverwrite())
            me.update(send_messages=True, view_channel=True)
            ow[guild.me] = me
        return ow

    # ------------------------------------------------------------------ găsire
    @staticmethod
    def _find_category(guild: discord.Guild, name: str) -> discord.CategoryChannel | None:
        exact = discord.utils.get(guild.categories, name=name)
        if exact:
            return exact
        return next((c for c in guild.categories if _norm(c.name) == _norm(name)), None)

    @staticmethod
    def _find_channel(category: discord.CategoryChannel, name: str):
        return next((c for c in category.channels if c.name == name or _norm(c.name) == _norm(name)), None)

    # ---------------------------------------------------------------- comanda
    @app_commands.command(name="configureaza-server", description="Creează rolurile, categoriile și canalele lipsă din config (nu șterge nimic).")
    @app_commands.describe(
        simulare="Doar arată ce s-ar face, fără să modifice serverul (implicit: da)",
        actualizeaza_permisiuni="Aplică permisiunile din config și pe categoriile/canalele care există deja",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def configure(self, interaction: discord.Interaction, simulare: bool = True, actualizeaza_permisiuni: bool = False):
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild
        assert guild is not None
        self.bot.cfg.reload()
        cfg = self.bot.cfg
        report: list[str] = ["SIMULARE – nu s-a modificat nimic." if simulare else "Modificări aplicate:"]
        reason = f"/configureaza-server de {interaction.user}"

        # 1. Roluri
        roles: dict[str, discord.Role] = {r.name: r for r in guild.roles}
        for spec in self._wanted_roles():
            if spec["name"] in roles:
                continue
            report.append(f"+ rol `{spec['name']}`")
            if not simulare:
                roles[spec["name"]] = await guild.create_role(
                    name=spec["name"], colour=_color(spec["color"]), hoist=bool(spec["hoist"]),
                    mentionable=True, reason=reason,
                )

        # 2. Categorii și canale
        position = 0
        for cat_spec in cfg.categories:
            category = self._find_category(guild, cat_spec.name)
            cat_ow = self._category_overwrites(guild, cat_spec, roles)
            if category is None:
                report.append(f"+ categorie **{cat_spec.name}**")
                if not simulare:
                    category = await guild.create_category(cat_spec.name, overwrites=cat_ow, reason=reason)
            elif actualizeaza_permisiuni:
                report.append(f"~ permisiuni categorie **{category.name}**")
                if not simulare:
                    await category.edit(overwrites=cat_ow, reason=reason)

            if category is not None and not simulare:
                try:
                    if category.position != position:
                        await category.edit(position=position, reason=reason)
                except discord.HTTPException:
                    pass
            position += 1

            for ch_spec in cat_spec.channels:
                existing = self._find_channel(category, ch_spec.name) if category else None
                if existing is not None:
                    want_forum = ch_spec.type == "forum"
                    if want_forum and not isinstance(existing, discord.ForumChannel):
                        report.append(
                            f"! `#{existing.name}` din {category.name} e canal text; în config e forum. "
                            "Discord nu permite conversia automată – vezi ghidul (merge și așa)."
                        )
                    if isinstance(existing, discord.ForumChannel) and not simulare:
                        await self._ensure_forum_tags(existing, report)
                    if actualizeaza_permisiuni and category is not None:
                        report.append(f"~ permisiuni `#{existing.name}`")
                        if not simulare:
                            await existing.edit(overwrites=self._channel_overwrites(guild, category, ch_spec, roles), reason=reason)
                    continue

                report.append(f"+ {ch_spec.type} `{ch_spec.name}` în {cat_spec.name}")
                if simulare or category is None:
                    continue
                ow = self._channel_overwrites(guild, category, ch_spec, roles)
                if ch_spec.type == "voce":
                    await guild.create_voice_channel(ch_spec.name, category=category, overwrites=ow, reason=reason)
                elif ch_spec.type == "forum":
                    try:
                        forum = await guild.create_forum(
                            ch_spec.name, category=category, overwrites=ow, topic=ch_spec.topic, reason=reason,
                        )
                        await self._ensure_forum_tags(forum, report)
                    except discord.HTTPException:
                        # Forumurile cer "Community" activat pe server; altfel facem canal text.
                        report.append(f"! `{ch_spec.name}` creat ca text (forumurile cer Community activat pe server)")
                        await guild.create_text_channel(ch_spec.name, category=category, overwrites=ow, topic=ch_spec.topic, reason=reason)
                else:
                    await guild.create_text_channel(ch_spec.name, category=category, overwrites=ow, topic=ch_spec.topic, reason=reason)

        # 3. Ce există pe server dar nu e în config (doar raportat)
        known = {_norm(c.name) for c in cfg.categories}
        extra = [c.name for c in guild.categories if _norm(c.name) not in known]
        if extra:
            report.append("")
            report.append("Categorii care nu sunt în config (nu le-am atins): " + ", ".join(f"**{n}**" for n in extra))
        orphans = [c.name for c in guild.channels if c.category is None and not isinstance(c, discord.CategoryChannel)]
        if orphans:
            report.append("Canale fără categorie: " + ", ".join(f"`{n}`" for n in orphans))

        if len(report) == 1:
            report.append("Totul este deja la zi. ✅")
        if simulare and len(report) > 1:
            report.append("\nDacă arată bine, rulează din nou cu `simulare: False`.")
        await self._send_report(interaction, "\n".join(report))

    async def _ensure_forum_tags(self, forum: discord.ForumChannel, report: list[str]) -> None:
        names = {t.name for t in forum.available_tags}
        missing = [t for t in self.bot.cfg.forum_tags if t not in names]
        if not missing:
            return
        tags = list(forum.available_tags) + [discord.ForumTag(name=t) for t in missing]
        await forum.edit(available_tags=tags[:20])
        report.append(f"+ etichete în `#{forum.name}`: {', '.join(missing)}")

    @staticmethod
    async def _send_report(interaction: discord.Interaction, text: str) -> None:
        if len(text) <= 1900:
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.followup.send(
                "Raportul e lung, l-am pus în fișier.",
                file=discord.File(io.BytesIO(text.encode()), filename="raport-configurare.txt"),
                ephemeral=True,
            )


async def setup(bot):
    await bot.add_cog(SetupServer(bot))
