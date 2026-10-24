import datetime
import random
import discord
from discord import app_commands
from discord.ext import commands

# Bot yetkilerini ayarlıyoruz
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- VERİ YAPILARI VE AYARLAR ---
# İstediklerini ekleyebilirsin
YASAKLI_KELIMELER = [
    "küfür1",
    "küfür2",
    "discord.gg/",
    "discord.com/invite/",
    "http://",
    "https://",
]
UYARILAR = {}  # {user_id: [sebep1, sebep2]}
AYARLAR = {"mod_log_id": None, "oto_rol_id": None}
MESAJ_TAKIP = {}  # Anti-Spam takibi için {user_id: [datetime, datetime]}


@bot.event
async def on_ready():
  print(f"{bot.user} olarak giriş yaptık! Güvenlik modülleri aktif.")
  try:
    synced = await bot.tree.sync()
    print(f" Toplam {len(synced)} adet Slash (/) komutu senkronize edildi.")
  except Exception as e:
    print(f"Komut senkronizasyon hatası: {e}")


# --- LOG GÖNDERME YARDIMCISI ---
async def log_gonder(guild, embed):
  log_id = AYARLAR.get("mod_log_id")
  if log_id:
    kanal = guild.get_channel(log_id)
    if kanal:
      await kanal.send(embed=embed)


# ==========================================
# 🚨 AUTOMATIC SECURITY & EVENT LISTENERS
# ==========================================


# 1. YENİ ÜYE KATILIM KORUMASI (Oto-Rol + Fake Hesap Koruması)
@bot.event
async def on_member_join(member):
  # Oto-Rol Ver
  rol_id = AYARLAR.get("oto_rol_id")
  if rol_id:
    rol = member.guild.get_role(rol_id)
    if rol:
      try:
        await member.add_roles(rol)
      except:
        pass

  # Fake / Şüpheli Hesap Kontrolü (3 günden yeni hesaplar)
  hesap_yasi = (discord.utils.utcnow() - member.created_at).days
  if hesap_yasi < 3:
    try:
      await member.kick(
          reason="Otomatik Güvenlik: Hesap yaşı 3 günden küçük."
      )
      embed = discord.Embed(
          title="🛡️ Şüpheli Hesap Sunucudan Atıldı",
          description=(
              f"**Kullanıcı:** {member.mention} ({member})\n**Hesap Yaşı:**"
              f" {hesap_yasi} gün"
          ),
          color=discord.Color.red(),
          timestamp=datetime.datetime.now(datetime.timezone.utc),
      )
      await log_gonder(member.guild, embed)
    except:
      pass


# 2. SİLİNEN MESAJ LOGU
@bot.event
async def on_message_delete(message):
  if message.author.bot or not message.guild:
    return
  embed = discord.Embed(
      title="🗑️ Mesaj Silindi",
      description=(
          f"**Kanal:** {message.channel.mention}\n**Yazan:**"
          f" {message.author.mention}\n**İçerik:** {message.content}"
      ),
      color=discord.Color.orange(),
      timestamp=datetime.datetime.now(datetime.timezone.utc),
  )
  await log_gonder(message.guild, embed)


# 3. DÜZENLENEN MESAJ LOGU
@bot.event
async def on_message_edit(before, after):
  if before.author.bot or before.content == after.content or not before.guild:
    return
  embed = discord.Embed(
      title="✏️ Mesaj Düzenlendi",
      description=(
          f"**Kanal:** {before.channel.mention}\n**Yazan:**"
          f" {before.author.mention}\n**Eski:** {before.content}\n**Yeni:**"
          f" {after.content}"
      ),
      color=discord.Color.blue(),
      timestamp=datetime.datetime.now(datetime.timezone.utc),
  )
  await log_gonder(before.guild, embed)


# 4. CHAT FİLTRESİ (Anti-Spam + Kötü Söz/Reklam + Oto-Selam)
@bot.event
async def on_message(message):
  if message.author.bot or not message.guild:
    return

  now = datetime.datetime.now()
  user_id = message.author.id

  # Yöneticiler filtrelere takılmaz
  is_admin = message.author.guild_permissions.administrator

  # --- ANTI-SPAM KONTROLÜ ---
  if not is_admin:
    if user_id not in MESAJ_TAKIP:
      MESAJ_TAKIP[user_id] = []

    # Son 3 saniye içinde atılan mesajları süz
    MESAJ_TAKIP[user_id] = [
        t for t in MESAJ_TAKIP[user_id] if (now - t).total_seconds() < 3
    ]
    MESAJ_TAKIP[user_id].append(now)

    if len(MESAJ_TAKIP[user_id]) >= 5:  # 3 saniyede 5 mesaj üstü
      try:
        sure = datetime.timedelta(minutes=5)
        await message.author.timeout(
            sure, reason="Otomatik Güvenlik: Spam Algılandı"
        )
        await message.channel.send(
            f"🚫 {message.author.mention}, spam yaptığın için **5 dakika**"
            " susturuldun!",
            delete_after=5,
        )
        return
      except:
        pass

  # --- REKLAM VE KÖTÜ SÖZ ENGELLİ ---
  icerik = message.content.lower().strip()
  if not is_admin:
    if any(kelime in icerik for kelime in YASAKLI_KELIMELER):
      try:
        await message.delete()
        await message.channel.send(
            f"⚠️ {message.author.mention}, bu kanalda reklam veya yasaklı"
            " kelime kullanamazsın!",
            delete_after=5,
        )
        return
      except:
        pass

  # --- OTOMATİK SELAM ---
  if icerik in ["sa", "s.a", "sa sa", "selam", "selamun aleykum"]:
    await message.channel.send(f"Aleykümselam, {message.author.mention}! 👋")

  await bot.process_commands(message)


# ==========================================
# ⚙️ SYSTEM SETTINGS COMMANDS
# ==========================================


@bot.tree.command(
    name="mod-log-ayarla", description="Mod-Log kanalını ayarlar."
)
@app_commands.checks.has_permissions(administrator=True)
async def mod_log_ayarla(
    interaction: discord.Interaction, kanal: discord.TextChannel
):
  AYARLAR["mod_log_id"] = kanal.id
  await interaction.response.send_message(
      f"✅ Log kanalı {kanal.mention} olarak ayarlandı.", ephemeral=True
  )


@bot.tree.command(
    name="oto-rol-ayarla",
    description="Girişte verilecek otomatik rolü ayarlar.",
)
@app_commands.checks.has_permissions(administrator=True)
async def oto_rol_ayarla(
    interaction: discord.Interaction, rol: discord.Role
):
  AYARLAR["oto_rol_id"] = rol.id
  await interaction.response.send_message(
      f"✅ Otomatik rol **{rol.name}** olarak ayarlandı.", ephemeral=True
  )


# ==========================================
# 🛡️ MODERATION & SECURITY COMMANDS
# ==========================================


# TEMİZLE
@bot.tree.command(
    name="temizle", description="Belirtilen miktarda mesajı siler."
)
@app_commands.checks.has_permissions(manage_messages=True)
async def temizle(interaction: discord.Interaction, miktar: int):
  if miktar < 1:
    await interaction.response.send_message(
        "En az 1 mesaj silmelisiniz.", ephemeral=True
    )
    return
  deleted = await interaction.channel.purge(limit=miktar)
  await interaction.response.send_message(
      f"🗑️ **{len(deleted)}** adet mesaj silindi.", ephemeral=True
  )


# KICK
@bot.tree.command(
    name="kick", description="Kullanıcıyı sunucudan atar."
)
@app_commands.checks.has_permissions(kick_members=True)
async def kick(
    interaction: discord.Interaction,
    uye: discord.Member,
    sebep: str = "Sebep belirtilmedi.",
):
  await uye.kick(reason=sebep)
  await interaction.response.send_message(
      f"🚪 **{uye.mention}** sunucudan atıldı. (Sebep: {sebep})"
  )


# BAN
@bot.tree.command(
    name="ban", description="Kullanıcıyı sunucudan yasaklar."
)
@app_commands.checks.has_permissions(ban_members=True)
async def ban(
    interaction: discord.Interaction,
    uye: discord.Member,
    sebep: str = "Sebep belirtilmedi.",
):
  await uye.ban(reason=sebep)
  await interaction.response.send_message(
      f"🔨 **{uye.mention}** sunucudan yasaklandı. (Sebep: {sebep})"
  )


# UNBAN
@bot.tree.command(
    name="unban", description="ID'si verilen kullanıcının banını kaldırır."
)
@app_commands.checks.has_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, kullanici_id: str):
  try:
    user = await bot.fetch_user(int(kullanici_id))
    await interaction.guild.unban(user)
    await interaction.response.send_message(
        f"🔓 **{user.name}** kullanıcısının banı kaldırıldı."
    )
  except Exception:
    await interaction.response.send_message(
        "❌ Kullanıcı bulunamadı veya banlı değil.", ephemeral=True
    )


# SUSTUR (TIMEOUT)
@bot.tree.command(
    name="sustur", description="Kullanıcıyı belirli dakika susturur."
)
@app_commands.checks.has_permissions(moderate_members=True)
async def sustur(
    interaction: discord.Interaction,
    uye: discord.Member,
    dakika: int,
    sebep: str = "Sebep belirtilmedi.",
):
  sure = datetime.timedelta(minutes=dakika)
  await uye.timeout(sure, reason=sebep)
  await interaction.response.send_message(
      f"🔇 **{uye.mention}**, {dakika} dakika susturuldu. (Sebep: {sebep})"
  )


# KANALI KİLİTLE
@bot.tree.command(
    name="kilitle", description="Bulunduğunuz kanalı mesaja kapatır."
)
@app_commands.checks.has_permissions(manage_channels=True)
async def kilitle(interaction: discord.Interaction):
  channel = interaction.channel
  overwrite = channel.overwrites_for(interaction.guild.default_role)
  overwrite.send_messages = False
  await channel.set_permissions(
      interaction.guild.default_role, overwrite=overwrite
  )
  await interaction.response.send_message("🔒 Kanal mesaja kilitlendi.")


# KANAL KİLİDİNİ AÇ
@bot.tree.command(
    name="kilit-ac", description="Kanalın kilit durumunu açar."
)
@app_commands.checks.has_permissions(manage_channels=True)
async def kilit_ac(interaction: discord.Interaction):
  channel = interaction.channel
  overwrite = channel.overwrites_for(interaction.guild.default_role)
  overwrite.send_messages = True
  await channel.set_permissions(
      interaction.guild.default_role, overwrite=overwrite
  )
  await interaction.response.send_message("🔓 Kanal kilitleri açıldı.")


# SLOWMODE
@bot.tree.command(
    name="slowmode", description="Kanalın mesaj hızı limitini ayarlar."
)
@app_commands.checks.has_permissions(manage_channels=True)
async def slowmode(interaction: discord.Interaction, saniye: int):
  await interaction.channel.edit(slowmode_delay=saniye)
  await interaction.response.send_message(
      f"⏱️ Yavaş mod **{saniye}** saniye yapıldı."
  )


# UYAR (WARN)
@bot.tree.command(
    name="uyar", description="Kullanıcıya resmi uyarı kaydı ekler."
)
@app_commands.checks.has_permissions(kick_members=True)
async def uyar(
    interaction: discord.Interaction, uye: discord.Member, sebep: str
):
  user_id = uye.id
  if user_id not in UYARILAR:
    UYARILAR[user_id] = []
  UYARILAR[user_id].append(sebep)
  await interaction.response.send_message(
      f"⚠️ **{uye.mention}** uyarıldı! (Sebep: {sebep}) | Toplam Uyarı:"
      f" **{len(UYARILAR[user_id])}**"
  )


# UYARILARI GÖSTER
@bot.tree.command(
    name="uyarilari-goster", description="Kullanıcının uyarılarını listeler."
)
@app_commands.checks.has_permissions(kick_members=True)
async def uyarilari_goster(
    interaction: discord.Interaction, uye: discord.Member
):
  user_id = uye.id
  if user_id not in UYARILAR or not UYARILAR[user_id]:
    await interaction.response.send_message(
        f"✅ **{uye.display_name}** kullanıcısının hiç uyarısı yok.",
        ephemeral=True,
    )
    return
  liste = "\n".join(
      [f"{i+1}. {sebep}" for i, sebep in enumerate(UYARILAR[user_id])]
  )
  embed = discord.Embed(
      title=f"⚠️ {uye.display_name} - Uyarı Geçmişi",
      description=liste,
      color=discord.Color.orange(),
  )
  await interaction.response.send_message(embed=embed, ephemeral=True)


# UYARILARI SİL
@bot.tree.command(
    name="uyari-sil", description="Kullanıcının tüm uyarılarını sıfırlar."
)
@app_commands.checks.has_permissions(kick_members=True)
async def uyari_sil(interaction: discord.Interaction, uye: discord.Member):
  if uye.id in UYARILAR:
    UYARILAR[uye.id] = []
  await interaction.response.send_message(
      f"✅ **{uye.mention}** uyarıları sıfırlandı.", ephemeral=True
  )


# KULLANICI BİLGİ
@bot.tree.command(
    name="kullanıcı-bilgi", description="Kullanıcının bilgilerini gösterir."
)
async def kullanici_bilgi(
    interaction: discord.Interaction, uye: discord.Member = None
):
  uye = uye or interaction.user
  embed = discord.Embed(
      title=f"👤 {uye.display_name} Bilgisi", color=discord.Color.blue()
  )
  embed.set_thumbnail(url=uye.display_avatar.url)
  embed.add_field(name="Kullanıcı Adı", value=str(uye), inline=True)
  embed.add_field(name="ID", value=uye.id, inline=True)
  embed.add_field(
      name="Hesap Oluşturulma",
      value=uye.created_at.strftime("%d/%m/%Y"),
      inline=False,
  )
  await interaction.response.send_message(embed=embed)


# HATA YAKALAMA (YETKİSİZ KULLANIM)
@temizle.error
@kick.error
@ban.error
@unban.error
@sustur.error
@kilitle.error
@kilit_ac.error
@slowmode.error
@uyar.error
@uyarilari_goster.error
@uyari_sil.error
@mod_log_ayarla.error
@oto_rol_ayarla.error
async def komut_hata(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
  if isinstance(error, app_commands.MissingPermissions):
    await interaction.response.send_message(
        "❌ Bu komut için gerekli yetkiye sahip değilsin!", ephemeral=True
    )


# BOT TOKENINIZI BURAYA YAZIN
bot.run("MTU2MzQ4OTAwODU0MDE4ODgyNA.GruILx.wxP2H652RifHginkteq47njrWiCk9WPVwb5f6s")
# MTU2MzQ4OTAwODU0MDE4ODgyNA.GruILx.wxP2H652RifHginkteq47njrWiCk9WPVwb5f6s