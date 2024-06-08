import discord
from discord.ext import commands
import wavelink
from embeds import *

intents = discord.Intents.default()  # Gives the bot all default intents
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.guild_messages = True

bot = commands.Bot(command_prefix='!', intents=intents)  # Initializes a bot instance with '!' prefix and all intents
bot.remove_command('help')  # Removes the generic help command from discord.ext

last_channel: int  # Variable to store last used channel
jumped: bool = False  # Variable to store if a jump command was run
cleared: bool = False  # Variable to store if a clear command was run
disconnected: bool = False  # Variable to store if a disconnect command was run
backed: bool = False  # Variable to store if a back command was run
played: bool = False  # Variable to store if a play command was run
track_looped: bool = False  # Variable to store if the track is looped or not


async def node_connect():  # Waits for the bot to get ready, then connects to a Lavalink node
    await bot.wait_until_ready()  # Wait until the bot is ready
    nodes = [wavelink.Node(identifier='Free Node', uri='https://lavalink4.alfari.id', password='catfein')]  # Free public node
    await wavelink.Pool.connect(nodes=nodes, client=bot)  # Connects to the node


async def check_user_in_vc(ctx):  # Checks if the user is in a voice channel

    if ctx.author.voice:
        return True
    else:
        await ctx.send(embed=user_not_in_vc)
        return False


async def user_bot_same_channel(ctx):  # Checks if the user and bot are in the same channel
    if ctx.author.voice.channel == ctx.guild.voice_client.channel:
        return True
    else:
        await ctx.send(embed=user_bot_channel)
        return False


@bot.event
async def on_command_error(ctx, error):  # Listener to catch unregistered commands
    if isinstance(error, discord.ext.commands.errors.CommandNotFound):
        await ctx.send(embed=not_a_command)


@bot.event
async def on_ready():  # Sends message to console when bot is ready
    print("==================")
    print("LoopyBot is ready!")
    print("==================")
    await bot.loop.create_task(node_connect())  # Runs function to connect to node after bot is ready


@bot.event
async def on_wavelink_node_ready(node: wavelink.node):  # Sends a message when the bot connects to a node successfully
    print("===============================")
    print("LoopyBot has connected to node!")
    print("===============================")


@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):  # Runs when a track or song ends.
    global played
    global cleared
    global jumped
    global track_looped
    global disconnected
    bot_vc: wavelink.Player() = payload.player
    current_queue: wavelink.Queue() = bot_vc.queue
    channel = bot.get_channel(last_channel)

    if track_looped:  # If the track is looped, it gets and replays the current song from the player.
        current_song = payload.track
        await bot_vc.play(current_song)
        now_playing = discord.Embed(title="**Now Playing**", description=f"**{current_song.title}** by **{current_song.author}**", color=0x9999FF)

        await channel.send(embed=now_playing)
    elif current_queue:  # Else, it checks if there is a song in queue.
        if not jumped and not backed and not played:  # Checks if a jump, back or play command was run
            next_song = current_queue.get()  # If no, it plays the next song
            await bot_vc.play(next_song)

            now_playing = discord.Embed(title="**Now Playing**", description=f"**{next_song.title}** by **{next_song.author}**", color=0x9999FF)
            await channel.send(embed=now_playing)
    elif not current_queue and not (cleared or backed or played or jumped):  # If the queue is empty and no clear, back, play or jump command was run, send an embed to tell the user the queue is empty
        await channel.send(embed=end_of_queue)


@bot.event
async def on_wavelink_inactive_player(player):  # Runs when the bot has been inactive for 15 minutes
    bot_vc: wavelink.Player() = player
    channel = bot.get_channel(last_channel)

    await channel.send(embed=bot_inactive)
    await bot_vc.disconnect()  # Disconnects after sending the relevant embed in the last channel used by the user.


@bot.command(name="play", aliases=["p", "pl", "plays"])
async def play(ctx, *, search_query: str = None):  # !play command, plays a song given by player
    global played
    global last_channel
    last_channel = ctx.message.channel.id  # Updates the last channel a command was sent
    if search_query is None:  # If user didn't provide a song, ask them for one.
        await ctx.send(embed=enter_song)
    else:
        in_channel = await check_user_in_vc(ctx)
        if in_channel:  # Checks if the user is in a voice channel
            if not ctx.guild.voice_client:  # If user is connected but bot is not, make bot join the user's channel
                await ctx.author.voice.channel.connect(cls=wavelink.Player)
                bot_vc: wavelink.Player() = ctx.voice_client
                bot_vc.inactive_timeout = 900  # The inactive timeout is set to 15 minutes (900 seconds)

                search: wavelink.Search = await wavelink.Playable.search(search_query)  # Searches for a track using user's input and Lavalink
                await bot_vc.play(track=search[0])  # Plays the track
                now_playing = discord.Embed(title="**Now Playing**", description=f"**{search[0].title}** by **{search[0].author}**", color=0x9999FF)
                await ctx.send(embed=now_playing)  # Sends the relevant embed
            elif await user_bot_same_channel(ctx):
                played = True
                bot_vc: wavelink.Player() = ctx.voice_client
                search: wavelink.Search = await wavelink.Playable.search(search_query)
                await bot_vc.play(track=search[0])

                now_playing = discord.Embed(title="**Now Playing**", description=f"**{search[0].title}** by **{search[0].author}**", color=0x9999FF)
                await ctx.send(embed=now_playing)
                played = False
            else:
                await ctx.send(embed=user_bot_channel)  # If user and bot are connected, but in different channels, send this embed.


@bot.command(name="queue", aliases=["q", "queues", "queued"])
async def queue(ctx, *, search_query: str = None):  # !queue command. Adds a song to queue if one is playing, else plays the song. Else if no song is given, display the queue.
    global last_channel
    last_channel = ctx.message.channel.id

    bot_vc: wavelink.Player() = ctx.voice_client

    in_channel = await check_user_in_vc(ctx)
    if in_channel:
        if not ctx.guild.voice_client:
            if search_query is None:
                await ctx.send(embed=empty_queue)
            else:
                await ctx.author.voice.channel.connect(cls=wavelink.Player)
                bot_vc: wavelink.Player() = ctx.voice_client
                bot_vc.inactive_timeout = 900

                search: wavelink.Search = await wavelink.Playable.search(search_query)
                await bot_vc.play(track=search[0])
                now_playing = discord.Embed(title="**Now Playing**", description=f"**{search[0].title}** by **{search[0].author}**", color=0x9999FF)
                await ctx.send(embed=now_playing)
        elif await user_bot_same_channel(ctx):
            current_queue: wavelink.Queue() = bot_vc.queue
            if search_query is None:
                if not current_queue.is_empty:
                    index = 0
                    queue_list = discord.Embed(title="**Songs in Queue**", description="Here are the first 10 songs that are currently in queue:")
                    if len(current_queue) < 10:  # If the queue has less than 10 songs in it, display all of them in order.
                        for i in current_queue:  # An iteration to add a new line to the embed for each song in queue.
                            queue_list.add_field(name='', value=f"{index+1}. **{current_queue.peek(index).title}** by **{current_queue.peek(index).author}**", inline=False)
                            index += 1
                        await ctx.send(embed=queue_list)
                    else:  # Otherwise, only display the first 10 songs queued.
                        for i in range(0, 11):
                            queue_list.add_field(name='', value=f"{index + 1}. **{current_queue.peek(index).title}** by **{current_queue.peek(index).author}**", inline=False)
                            index += 1
                elif not current_queue:
                    await ctx.send(embed=empty_queue)
            else:
                if bot_vc.playing or bot_vc.paused:
                    search: wavelink.Search = await wavelink.Playable.search(search_query)
                    current_queue.put(search[0])
                    queued = discord.Embed(title="**Added to Queue**", description=f"**{search[0].title}** by **{search[0].author}**", color=0x9999FF)
                    await ctx.send(embed=queued)
                else:  # If no song is playing or paused, and the queue is empty, the command behaves like !play
                    search: wavelink.Search = await wavelink.Playable.search(search_query)
                    await bot_vc.play(search[0])
                    now_playing = discord.Embed(title="**Now Playing**", description=f"**{search[0].title}** by **{search[0].author}**", color=0x9999FF)
                    await ctx.send(embed=now_playing)
        else:
            await ctx.send(embed=user_bot_channel)


@bot.command(name="skip", aliases=["s", "sk", "skipp", "skipped", "skips"])
async def skip(ctx):  # Either skips to the next song in queue or stops the player if there are none in queue.
    global last_channel
    global track_looped
    last_channel = ctx.message.channel.id

    bot_vc: wavelink.Player() = ctx.voice_client

    in_channel = await check_user_in_vc(ctx)
    if in_channel:
        if not ctx.guild.voice_client:
            await ctx.send(embed=bot_not_in_vc)
        elif await user_bot_same_channel(ctx):
            current_queue: wavelink.Queue = bot_vc.queue
            if current_queue:
                if bot_vc.playing or bot_vc.paused and not track_looped:
                    await bot_vc.skip(force=True)
                    await ctx.send(embed=skipped_song)
                elif bot_vc.playing or bot_vc.paused and track_looped:
                    await bot_vc.skip(force=True)
                    await ctx.send(embed=skip_looped)
                else:
                    await ctx.send(embed=mythic_error)  # This error is not supposed to happen in any circumstance.
            elif not current_queue:
                if bot_vc.playing or bot_vc.paused:
                    await bot_vc.skip(force=True)
                else:
                    await ctx.send(embed=nothing_to_skip)


@bot.command(name="pause", aliases=["pauses", "paused", "pa"])
async def pause(ctx):  # Pauses the current song if any is playing, else send the relevant embed.
    global last_channel
    last_channel = ctx.message.channel.id
    bot_vc: wavelink.Player() = ctx.voice_client
    in_channel = await check_user_in_vc(ctx)
    if in_channel:
        if ctx.guild.voice_client:
            if ctx.guild.voice_client.channel == ctx.author.voice.channel:
                if not bot_vc.paused:
                    await bot_vc.pause(True)
                    await ctx.send(embed=pause_success)
                elif bot_vc.paused:
                    await ctx.send(embed=bot_is_paused)
                else:
                    await ctx.send(embed=no_song_playing)
            else:
                await ctx.send(embed=user_bot_channel)
        else:
            await ctx.send(embed=bot_not_in_vc)


@bot.command(name="unpause", aliases=["unpauses", "unpaused", "unpa"])
async def unpause(ctx):  # Unpauses the current song if any is paused, else send the relevant embed.
    global last_channel
    last_channel = ctx.message.channel.id
    bot_vc: wavelink.Player() = ctx.voice_client
    in_channel = await check_user_in_vc(ctx)
    if in_channel:
        if ctx.guild.voice_client:
            if ctx.guild.voice_client.channel == ctx.author.voice.channel:
                if bot_vc.paused:
                    await bot_vc.pause(False)
                    await ctx.send(embed=unpause_success)
                elif not bot_vc.paused:
                    await ctx.send(embed=bot_is_unpaused)
                else:
                    await ctx.send(embed=no_song_playing)
            else:
                await ctx.send(embed=user_bot_channel)
        else:
            await ctx.send(embed=bot_not_in_vc)


@bot.command(name="jump", aliases=["j", "jumped", "jumps", "jumpp"])
async def jump(ctx, position: int = None):  # Deletes songs in queue before the given position and plays the song in the position.
    global last_channel
    global jumped
    last_channel = ctx.message.channel.id
    bot_vc: wavelink.Player() = ctx.voice_client
    if position is None:
        await ctx.send(embed=enter_jump_position)
    else:
        in_channel = await check_user_in_vc(ctx)
        if in_channel:
            if not ctx.guild.voice_client:
                await ctx.send(embed=bot_not_in_vc)
            elif ctx.guild.voice_client.channel == ctx.author.voice.channel:
                current_queue: wavelink.Queue() = bot_vc.queue
                if position > len(current_queue):  # Checks if the position exists within the queue
                    await ctx.send(embed=invalid_position)
                else:
                    if track_looped:  # If the track is looped, jumping will break it.
                        await ctx.send(embed=cannot_jump_loop)
                    else:
                        for i in range(position-1):  # Deletes all queued songs before the given position.
                            current_queue.delete(0)
                        new_song = current_queue.get()  # Gets and plays the next song
                        jumped = True
                        await bot_vc.play(new_song)
                        now_playing = discord.Embed(title="**Jumping To Song**", description=f"**{new_song.title}** by **{new_song.author}**", color=0x9999FF)
                        await ctx.send(embed=now_playing)
                        jumped = False
            else:
                await ctx.send(embed=user_bot_channel)


@bot.command(name="clear", aliases=["c", "cl", "clears", "clearr"])
async def clear(ctx):  # Clears the queue and it's history
    global cleared
    global last_channel
    last_channel = ctx.message.channel.id
    bot_vc: wavelink.Player() = ctx.voice_client
    current_queue: wavelink.Queue() = bot_vc.queue

    in_channel = await check_user_in_vc(ctx)
    if in_channel:
        if not ctx.guild.voice_client:
            await ctx.send(embed=bot_not_in_vc)
        elif ctx.author.voice.channel == ctx.guild.voice_client.channel:
            if not current_queue and not (bot_vc.playing or bot_vc.paused) and not disconnected:
                await ctx.send(embed=empty_queue)
            else:
                cleared = True
                current_queue.reset()
                if bot_vc.playing or bot_vc.paused:
                    await bot_vc.skip()
                if not disconnected:  # Used to check whether this was called through the !disconnect command
                    await ctx.send(embed=queue_cleared)
                cleared = False
        else:
            await ctx.send(embed=user_bot_channel)


@bot.command(name="disconnect", aliases=["dc", "disc", "quit", "disconnected"])
async def disconnect(ctx):  # Clears the queue and disconnects the bot from the voice channel
    global disconnected
    global last_channel
    last_channel = ctx.message.channel.id
    bot_vc: wavelink.Player() = ctx.voice_client
    in_channel = await check_user_in_vc(ctx)
    if in_channel:
        if not ctx.guild.voice_client:
            await ctx.send(embed=bot_not_in_vc)
        elif ctx.author.voice.channel == ctx.guild.voice_client.channel:
            disconnected = True
            await clear(ctx)  # Calls the !clear command internally to clear the queue
            if bot_vc.playing or bot_vc.paused:
                await bot_vc.stop()
            await bot_vc.disconnect()
            await ctx.send(embed=disconnected_success)
            disconnected = False
        else:
            await ctx.send(embed=user_bot_channel)


@bot.command(name="back", aliases=["b", "ba"])
async def back(ctx):  # Plays the last played song and puts the current song back in the first index of the queue.
    global backed
    global last_channel
    last_channel = ctx.message.channel.id
    bot_vc: wavelink.Player() = ctx.voice_client
    current_queue: wavelink.Queue() = bot_vc.queue
    history_queue: wavelink.Queue() = current_queue.history
    in_channel = await check_user_in_vc(ctx)
    if in_channel:
        if not ctx.guild.voice_client:
            await ctx.send(embed=bot_not_in_vc)
        elif ctx.author.voice.channel == ctx.guild.voice_client.channel:
            if not history_queue:
                await ctx.send(embed=no_prev_song)
            else:
                backed = True
                current_track = bot_vc.current
                back_track = history_queue.get_at(len(history_queue)-2)
                if current_track is not None:
                    current_queue.put_at(0, current_track)
                await bot_vc.play(back_track)

                now_playing = discord.Embed(title="**Now Playing Last Song**", description=f"**{back_track.title}** by **{back_track.author}**", color=0x9999FF)
                await ctx.send(embed=now_playing)
                backed = False
        else:
            await ctx.send(embed=user_bot_channel)


@bot.command(name="loop", aliases=["lp", "looped", "track"])
async def loop(ctx):  # Loops the track if it is not looped and vice versa
    global last_channel
    global track_looped
    last_channel = ctx.message.channel.id

    in_channel = await check_user_in_vc(ctx)
    if in_channel:
        if not ctx.guild.voice_client:
            await ctx.send(embed=bot_not_in_vc)
        elif ctx.author.voice.channel == ctx.guild.voice_client.channel:
            if not track_looped:
                track_looped = True
                await ctx.send(embed=loop_track)
            else:
                track_looped = False
                await ctx.send(embed=unloop_successful)
        else:
            await ctx.send(embed=user_bot_channel)


@bot.command(name="unqueue", aliases=["unq", "unqueued", "uq"])
async def unqueue(ctx, position: int = None):  # Removes a specific song from queue at the given position
    global last_channel
    last_channel = ctx.message.channel.id
    bot_vc: wavelink.Player() = ctx.voice_client
    current_queue: wavelink.Queue() = bot_vc.queue

    if position is None:
        await ctx.send(embed=enter_unqueue_position)
    else:
        in_channel = await check_user_in_vc(ctx)
        if in_channel:
            if not ctx.guild.voice_client:
                await ctx.send(embed=bot_not_in_vc)
            elif ctx.author.voice.channel == ctx.guild.voice_client.channel:
                if position > len(current_queue):  # Checks if the position given exists within the queue
                    await ctx.send(embed=invalid_position)
                else:
                    current_queue.delete(position-1)
                    await queue(ctx)
            else:
                await ctx.send(embed=user_bot_channel)


@bot.command(name="help", aliases=["h", "Help", "helpp"])
async def help(ctx):  # The help command that lists all possible commands
    await ctx.send(embed=command_list)


if __name__ == '__main__':
    bot.run('BOTTOKEN')
