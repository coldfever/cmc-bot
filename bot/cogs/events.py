"""Evenimente și turnee: anunț cu butoane de înscriere, limită de locuri, remindere, rezultate."""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

STATUS_LABEL = {"da": "✅ Vin", "poate": "🤔 Poate", "nu": "❌ Nu vin"}


def parse_when(data: str, ora: str, tz) -> datetime:
    data = data.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m"):
        try:
            d = datetime.strptime(data, fmt)
            if fmt == "%d.%m":
                d = d.replace(year=datetime.now(tz).year)
            break
        except ValueError:
            continue
    else:
        raise ValueError("Data trebuie să fie de forma 12.11.2026")
    m = re.fullmatch(r"(\d{1,2})[:.](\d{2})", ora.strip())
    if not m:
        raise ValueError("Ora trebuie să fie de forma 18:00")
    return d.replace(hour=int(m.group(1)), minute=int(m.group(2)), tzinfo=tz)


async def game_autocomplete(interaction: discord.Interaction, current: str):
    games = interaction.client.cfg.games
    return [
        app_commands.Choice(name=g.name, value=g.key)
        for g in games
        if current.lower() in g.name.lower()
    ][:25]


class RSVPButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cmc:rsvp:(?P<event>\d+):(?P<status>da|poate|nu)"):
    def __init__(self, event_id: int, status: str):
        style = {"da": discord.ButtonStyle.success, "poate": discord.ButtonStyle.secondary, "nu": discord.ButtonStyle.danger}[status]
        super().__init__(discord.ui.Button(label=STATUS_LABEL[status], style=style, custom_id=f"cmc:rsvp:{event_id}:{status}"))
        self.event_id = event_id
        self.status = status

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["event"]), match["status"])

    async def callback(self, interaction: discord.Interaction):
        cog: Events = interaction.client.get_cog("Events")
        await cog.handle_rsvp(interaction, self.event_id, self.status)


def rsvp_view(event_id: int, disabled: bool = False) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    for s in ("da", "poate", "nu"):
        item = RSVPButton(event_id, s)
        item.item.disabled = disabled
        view.add_item(item)
    return view


class Events(commands.Cog):
    eveniment = app_commands.Group(name="eveniment", description="Turnee și seri de joc", guild_only=True)

    def __init__(self, bot):
        self.bot = bot
        bot.add_dynamic_items(RSVPButton)
        self.reminders.start()

    def cog_unload(self):
        self.reminders.cancel()

    # ------------------------------------------------------------ utilitare
    async def _event(self, event_id: int):
        async with self.bot.db.execute("SELECT * FROM events WHERE id = ?", (event_id,)) as cur:
            return await cur.fetchone()

    async def _rsvps(self, event_id: int) -> dict[str, list[int]]:
        out = {"da": [], "poate": [], "nu": []}
        async with self.bot.db.execute(
            "SELECT user_id, status FROM rsvps WHERE event_id = ? ORDER BY created_at", (event_id,)
        ) as cur:
            async for row in cur:
                out[row["status"]].append(row["user_id"])
        return out

    async def build_embed(self, ev) -> discord.Embed:
        game = self.bot.cfg.game(ev["game"]) if ev["game"] else None
        r = await self._rsvps(ev["id"])
        ts = ev["starts_at"]
        title = f"{game.emoji} {ev['title']}" if game and game.emoji else ev["title"]
        if ev["cancelled"]:
            title = f"[ANULAT] {title}"
        embed = discord.Embed(title=title, description=ev["description"] or None, colour=discord.Colour.orange())
        embed.add_field(name="Când", value=f"<t:{ts}:F>\n(<t:{ts}:R>)", inline=True)
        if game:
            embed.add_field(name="Joc", value=game.name, inline=True)
        cap = ev["capacity"]
        going = r["da"]
        confirmed, waitlist = (going[:cap], going[cap:]) if cap else (going, [])
        label = f"Vin ({len(confirmed)}/{cap})" if cap else f"Vin ({len(confirmed)})"
        embed.add_field(name=label, value=" ".join(f"<@{u}>" for u in confirmed[:40]) or "—", inline=False)
        if waitlist:
            embed.add_field(name=f"Listă de așteptare ({len(waitlist)})", value=" ".join(f"<@{u}>" for u in waitlist[:40]), inline=False)
        if r["poate"]:
            embed.add_field(name=f"Poate ({len(r['poate'])})", value=" ".join(f"<@{u}>" for u in r["poate"][:40]), inline=False)
        embed.set_footer(text=f"Eveniment #{ev['id']}")
        return embed

    async def refresh_message(self, ev) -> None:
        guild = self.bot.get_guild(ev["guild_id"])
        channel = guild and guild.get_channel(ev["channel_id"])
        if not channel or not ev["message_id"]:
            return
        try:
            msg = await channel.fetch_message(ev["message_id"])
            closed = bool(ev["cancelled"]) or ev["starts_at"] < time.time()
            await msg.edit(embed=await self.build_embed(ev), view=rsvp_view(ev["id"], disabled=closed))
        except discord.HTTPException:
            pass

    async def handle_rsvp(self, interaction: discord.Interaction, event_id: int, status: str):
        ev = await self._event(event_id)
        if ev is None or ev["cancelled"]:
            await interaction.response.send_message("Evenimentul nu mai este activ.", ephemeral=True)
            return
        if ev["starts_at"] < time.time():
            await interaction.response.send_message("Evenimentul a început deja.", ephemeral=True)
            return
        cap = ev["capacity"]
        before = (await self._rsvps(event_id))["da"][:cap] if cap else []
        await self.bot.db.execute(
            "INSERT INTO rsvps(event_id, user_id, status, created_at) VALUES (?,?,?,?) "
            "ON CONFLICT(event_id, user_id) DO UPDATE SET status = excluded.status, "
            "created_at = CASE WHEN rsvps.status = excluded.status THEN rsvps.created_at ELSE excluded.created_at END",
            (event_id, interaction.user.id, status, time.time()),
        )
        await self.bot.db.commit()
        r = await self._rsvps(event_id)
        msg = {"da": "Te-am trecut la **Vin**.", "poate": "Te-am trecut la **Poate**.", "nu": "Te-am trecut la **Nu vin**."}[status]
        if status == "da" and ev["capacity"] and interaction.user.id in r["da"][ev["capacity"]:]:
            msg = "Locurile sunt ocupate, ești pe **lista de așteptare**. Te anunț dacă se eliberează un loc."
        await interaction.response.send_message(msg, ephemeral=True)
        await self.refresh_message(ev)
        if cap:
            promoted = [u for u in r["da"][:cap] if u not in before and u != interaction.user.id]
            if promoted and interaction.channel:
                await interaction.channel.send(
                    f"🎟️ S-a eliberat un loc la **{ev['title']}**: " + " ".join(f"<@{u}>" for u in promoted) + " ești acum pe lista de participanți."
                )

    # ------------------------------------------------------------ comenzi
    @eveniment.command(name="creeaza", description="Anunță un turneu sau o seară de joc, cu înscriere.")
    @app_commands.describe(
        titlu="Ex: Turneu Pokemon Standard",
        data="Ex: 12.11.2026",
        ora="Ex: 18:00",
        joc="Jocul (decide unde se anunță și cine primește ping)",
        descriere="Format, taxă, premii etc.",
        locuri="Număr maxim de participanți (gol = nelimitat)",
        ping="Pe cine anunț: rolul competitiv, rolul jocului sau pe nimeni",
        durata_ore="Durata, pentru calendarul Discord (implicit 4)",
    )
    @app_commands.autocomplete(joc=game_autocomplete)
    @app_commands.choices(ping=[
        app_commands.Choice(name="Rolul competitiv", value="competitiv"),
        app_commands.Choice(name="Toți jucătorii jocului", value="joc"),
        app_commands.Choice(name="Fără ping", value="nimeni"),
    ])
    @app_commands.checks.has_permissions(manage_events=True)
    async def create(self, interaction: discord.Interaction, titlu: str, data: str, ora: str, joc: str | None = None,
                     descriere: str | None = None, locuri: app_commands.Range[int, 1, 500] | None = None,
                     ping: str = "competitiv", durata_ore: app_commands.Range[int, 1, 24] = 4):
        cfg = self.bot.cfg
        try:
            when = parse_when(data, ora, cfg.tz)
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return
        if when.timestamp() < time.time():
            await interaction.response.send_message("Data este în trecut.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        game = cfg.game(joc) if joc else None
        channel = None
        if game and game.announce_channel:
            channel = self.bot.channel_by_name(guild, game.announce_channel, game.category)
        channel = channel or self.bot.bot_channel(guild, "evenimente") or interaction.channel

        cur = await self.bot.db.execute(
            "INSERT INTO events(guild_id, channel_id, title, game, description, starts_at, capacity, created_by) VALUES (?,?,?,?,?,?,?,?)",
            (guild.id, channel.id, titlu, game.key if game else None, descriere, int(when.timestamp()), locuri, interaction.user.id),
        )
        await self.bot.db.commit()
        ev = await self._event(cur.lastrowid)

        mention = ""
        if game and ping != "nimeni":
            role_name = game.competitive_role if ping == "competitiv" and game.competitive_role else game.role
            role = discord.utils.get(guild.roles, name=role_name)
            mention = role.mention if role else ""
        msg = await channel.send(
            content=mention or None,
            embed=await self.build_embed(ev),
            view=rsvp_view(ev["id"]),
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
        await self.bot.db.execute("UPDATE events SET message_id = ? WHERE id = ?", (msg.id, ev["id"]))
        await self.bot.db.commit()

        # Apare și în calendarul serverului (Evenimente), dacă botul are permisiune.
        extra = ""
        try:
            await guild.create_scheduled_event(
                name=titlu[:100], start_time=when, end_time=when + timedelta(hours=durata_ore),
                entity_type=discord.EntityType.external, location="Critical Miss Club",
                privacy_level=discord.PrivacyLevel.guild_only, description=(descriere or "")[:1000],
            )
        except discord.HTTPException:
            extra = " (nu am putut adăuga în calendarul Discord – verifică permisiunea Manage Events)"
        await interaction.followup.send(f"Eveniment #{ev['id']} anunțat în {channel.mention}{extra}.", ephemeral=True)

    @eveniment.command(name="anuleaza", description="Anulează un eveniment și anunță participanții.")
    @app_commands.checks.has_permissions(manage_events=True)
    async def cancel(self, interaction: discord.Interaction, id: int, motiv: str | None = None):
        ev = await self._event(id)
        if ev is None:
            await interaction.response.send_message("Nu există evenimentul.", ephemeral=True)
            return
        await self.bot.db.execute("UPDATE events SET cancelled = 1 WHERE id = ?", (id,))
        await self.bot.db.commit()
        ev = await self._event(id)
        await self.refresh_message(ev)
        r = await self._rsvps(id)
        channel = interaction.guild.get_channel(ev["channel_id"])
        if channel and (r["da"] or r["poate"]):
            people = " ".join(f"<@{u}>" for u in (r["da"] + r["poate"])[:80])
            await channel.send(f"❌ **{ev['title']}** a fost anulat. {motiv or ''}\n{people}")
        await interaction.response.send_message("Anulat.", ephemeral=True)

    @eveniment.command(name="participanti", description="Lista de înscriși (doar pentru tine).")
    @app_commands.checks.has_permissions(manage_events=True)
    async def attendees(self, interaction: discord.Interaction, id: int):
        ev = await self._event(id)
        if ev is None:
            await interaction.response.send_message("Nu există evenimentul.", ephemeral=True)
            return
        r = await self._rsvps(id)
        guild = interaction.guild
        def names(ids):
            return "\n".join(f"{i+1}. {(guild.get_member(u).display_name if guild.get_member(u) else u)}" for i, u in enumerate(ids)) or "—"
        await interaction.response.send_message(
            f"**{ev['title']}**\n\n**Vin ({len(r['da'])})**\n{names(r['da'])}\n\n**Poate ({len(r['poate'])})**\n{names(r['poate'])}"[:1990],
            ephemeral=True,
        )

    @eveniment.command(name="lista", description="Evenimentele care urmează.")
    async def upcoming(self, interaction: discord.Interaction):
        async with self.bot.db.execute(
            "SELECT * FROM events WHERE guild_id = ? AND cancelled = 0 AND starts_at > ? ORDER BY starts_at LIMIT 15",
            (interaction.guild.id, int(time.time())),
        ) as cur:
            rows = await cur.fetchall()
        if not rows:
            await interaction.response.send_message("Nu sunt evenimente programate.", ephemeral=True)
            return
        lines = [f"#{r['id']} · <t:{r['starts_at']}:f> · **{r['title']}**" for r in rows]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="rezultate", description="Publică rezultatele unui turneu în #rezultate-turnee.")
    @app_commands.describe(titlu="Ex: Turneu One Piece 12.11", clasament="Ex: 1. Ana 2. Mihai 3. Dan (poți folosi \\n)", poza="Poză opțională")
    @app_commands.autocomplete(joc=game_autocomplete)
    @app_commands.default_permissions(manage_events=True)
    @app_commands.guild_only()
    async def results(self, interaction: discord.Interaction, titlu: str, clasament: str, joc: str | None = None,
                      poza: discord.Attachment | None = None):
        channel = self.bot.bot_channel(interaction.guild, "rezultate") or interaction.channel
        game = self.bot.cfg.game(joc) if joc else None
        embed = discord.Embed(
            title=f"🏆 {titlu}",
            description=clasament.replace("\\n", "\n"),
            colour=discord.Colour.gold(),
        )
        if game:
            embed.set_author(name=f"{game.emoji} {game.name}")
        if poza:
            embed.set_image(url=poza.url)
        await channel.send(embed=embed)
        await interaction.response.send_message(f"Publicat în {channel.mention}.", ephemeral=True)

    # ------------------------------------------------------------ remindere
    @tasks.loop(minutes=1)
    async def reminders(self):
        now = int(time.time())
        for col, window, text in (("reminded_24h", 24 * 3600, "mâine"), ("reminded_1h", 3600, "într-o oră")):
            async with self.bot.db.execute(
                f"SELECT * FROM events WHERE cancelled = 0 AND {col} = 0 AND starts_at > ? AND starts_at <= ?",
                (now, now + window),
            ) as cur:
                rows = await cur.fetchall()
            for ev in rows:
                await self.bot.db.execute(f"UPDATE events SET {col} = 1 WHERE id = ?", (ev["id"],))
                await self.bot.db.commit()
                # dacă evenimentul a fost creat cu mai puțin de 24h înainte, nu trimitem reminderul de 24h
                if col == "reminded_24h" and ev["starts_at"] - now < 3 * 3600:
                    continue
                r = await self._rsvps(ev["id"])
                going = r["da"][: ev["capacity"]] if ev["capacity"] else r["da"]
                guild = self.bot.get_guild(ev["guild_id"])
                channel = guild and guild.get_channel(ev["channel_id"])
                if channel and going:
                    people = " ".join(f"<@{u}>" for u in going[:80])
                    await channel.send(f"⏰ **{ev['title']}** începe {text} (<t:{ev['starts_at']}:t>). {people}")
        # dezactivează butoanele evenimentelor începute (o singură dată)
        async with self.bot.db.execute(
            "SELECT * FROM events WHERE cancelled = 0 AND starts_at <= ? AND starts_at > ?", (now, now - 60)
        ) as cur:
            for ev in await cur.fetchall():
                await self.refresh_message(ev)

    @reminders.before_loop
    async def _wait(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Events(bot))
