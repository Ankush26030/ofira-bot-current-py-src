import discord
from discord.ext import commands
import wavelink


def in_voice():
    """Check if user is in a voice channel"""
    async def predicate(ctx: commands.Context):
        if not ctx.author.voice:
            raise commands.CheckFailure("You need to be in a voice channel to use this command!")
        return True
    return commands.check(predicate)


def bot_in_voice():
    """Check if bot is in a voice channel"""
    async def predicate(ctx: commands.Context):
        if not ctx.guild.voice_client:
            raise commands.CheckFailure("I'm not in a voice channel!")
        return True
    return commands.check(predicate)


def same_voice():
    """Check if user and bot are in the same voice channel"""
    async def predicate(ctx: commands.Context):
        if not ctx.author.voice:
            raise commands.CheckFailure("You need to be in a voice channel!")
        
        if ctx.guild.voice_client and ctx.author.voice.channel != ctx.guild.voice_client.channel:
            raise commands.CheckFailure("You need to be in the same voice channel as me!")
        
        return True
    return commands.check(predicate)


def is_playing():
    """Check if a track is currently playing"""
    async def predicate(ctx: commands.Context):
        player: wavelink.Player = ctx.guild.voice_client
        if not player or not player.current:
            raise commands.CheckFailure("Nothing is playing right now!")
        return True
    return commands.check(predicate)
