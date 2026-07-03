    async def show_level(self, ctx: commands.Context, member: discord.Member = None):
            """Displays the user's current level, XP, and customizable progress bar."""
            member = member or ctx.author
            if member.bot:
                await ctx.send("🤖 Bots don't have XP levels!")
                return
    
            guild_id = str(ctx.guild.id)
            user_id = str(member.id)
            await ctx.trigger_typing()
            
            loop = asyncio.get_running_loop()
    
            def fetch_guild_and_user_data():
                g_sheet = self.get_sheet("guilds")
                g_rows = g_sheet.get_all_values()
                g_row = next((r for r in g_rows[1:] if r and r[0] == guild_id), None)
                
                custom_enabled = g_row[6] == "True" if g_row and len(g_row) > 6 else False
                embed_title = g_row[7] if g_row and len(g_row) > 7 and g_row[7] else "✨ {name}'s Level Progress"
                border_hex = g_row[8] if g_row and len(g_row) > 8 and g_row[8] else "purple"
                filled_emoji = g_row[9] if g_row and len(g_row) > 9 and g_row[9] else "🟩"
                empty_emoji = g_row[10] if g_row and len(g_row) > 10 and g_row[10] else "⬛"
    
                is_first_use = g_row is None or len(g_row) <= 6 or g_row[6] == ""
    
                user_sheet = self.get_sheet("user_roles")
                user_records = user_sheet.get_all_values()
                user_row = next((r for r in user_records[1:] if r and r[0] == guild_id and r[1] == user_id), None)
                
                current_xp = int(user_row[3]) if user_row and len(user_row) > 3 else 0
                current_level = int(user_row[4]) if user_row and len(user_row) > 4 else 1
                
                curve_sheet = self.get_sheet("level_xp")
                curves = {r[1]: int(r[2]) for r in curve_sheet.get_all_values()[1:] if r and r[0] == guild_id}
                xp_needed_for_next = curves.get(str(current_level), 100)
    
                return is_first_use, custom_enabled, embed_title, border_hex, filled_emoji, empty_emoji, current_xp, current_level, xp_needed_for_next
    
            (is_first_use, custom_enabled, embed_title, border_hex, 
             filled_emoji, empty_emoji, current_xp, current_level, xp_needed_for_next) = await loop.run_in_executor(None, fetch_guild_and_user_data)
    
            if is_first_use:
                if not ctx.author.guild_permissions.manage_guild:
                    await ctx.send("This server's level tracker layout hasn't been configured by an Administrator yet.")
                    return
                    
                prompt_view = CustomTrackerPromptView(self, guild_id)
                await ctx.send(
                    "**First Use Detected!** Would you like to set up a custom layout for your server's level embeds?", 
                    view=prompt_view
                )
                return
    
            if xp_needed_for_next <= 0:
                xp_needed_for_next = 100
            progress_ratio = min(current_xp / xp_needed_for_next, 1.0)
            
            bar_length = 10
            filled_blocks = int(progress_ratio * bar_length)
            empty_blocks = bar_length - filled_blocks
            progress_bar = (filled_emoji * filled_blocks) + (empty_emoji * empty_blocks)
            percentage = int(progress_ratio * 100)
    
            embed_color = discord.Color.purple()
            if custom_enabled:
                try:
                    if border_hex.startswith("#"):
                        embed_color = discord.Color.from_str(border_hex)
                    else:
                        embed_color = getattr(discord.Color, border_hex.lower())()
                except Exception:
                    embed_color = discord.Color.purple()
    
            formatted_title = embed_title.replace("{name}", member.display_name).replace("{level}", str(current_level))
    
            embed = discord.Embed(title=formatted_title, color=embed_color)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name=" Level", value=f"`{current_level}`", inline=True)
            embed.add_field(name=" Experience", value=f"`{current_xp} / {xp_needed_for_next} XP`", inline=True)
            embed.add_field(name=f" Progress to Level {current_level + 1} ({percentage}%)", value=progress_bar, inline=False)
            embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
    
            await ctx.send(embed=embed)