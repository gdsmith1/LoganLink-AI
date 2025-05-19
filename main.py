import discord
from discord.ext import commands
import os
import openai
import asyncio
import io
import dotenv
from elevenlabs.client import ElevenLabs

dotenv.load_dotenv()

# Verify environment variables
required_env_vars = ['OPENAI_API_KEY', 'ELEVENLABS_API_KEY', 'DISCORD_BOT_TOKEN']
for var in required_env_vars:
    if not os.getenv(var):
        raise ValueError(f"Missing required environment variable: {var}")

# Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# API Clients
openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
elevenlabs_client = ElevenLabs(api_key=os.getenv('ELEVENLABS_API_KEY'))

# Global variables
is_voice_active = False
voice_client = None
MODEL_ID = "ft:gpt-3.5-turbo-0125:personal:20250330200835:BH0ak1o7"
VOICE_ID = "kGJWdLyKtBz7loQik2lE"

def generate_audio(text):
    """Helper function to generate audio using ElevenLabs"""
    audio_stream = elevenlabs_client.text_to_speech.convert_as_stream(
        voice_id=VOICE_ID,
        output_format="mp3_44100_128",
        text=text,
        model_id="eleven_multilingual_v2",
    )
    audio_bytes = io.BytesIO()
    for chunk in audio_stream:
        audio_bytes.write(chunk)
    audio_bytes.seek(0)
    return audio_bytes

async def play_audio(ctx, audio_bytes):
    """Plays audio in voice channel if voice is active"""
    global voice_client
    if not is_voice_active:
        return
    if voice_client and voice_client.is_connected():
        if voice_client.is_playing():
            voice_client.stop()
        temp_file = "temp_audio.mp3"
        with open(temp_file, "wb") as f:
            f.write(audio_bytes.getvalue())
        voice_client.play(discord.FFmpegPCMAudio(temp_file))
        while voice_client.is_playing():
            await asyncio.sleep(0.1)
        os.remove(temp_file)

@bot.group()
async def loganlink(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send('Invalid loganlink command passed. Use one of: activate, deactivate, say, chat, talk, repeat.')

@loganlink.command()
async def activate(ctx):
    """Activates the bot and joins your voice channel"""
    global is_voice_active, voice_client
    try:
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            voice_client = await channel.connect()
            is_voice_active = True
            audio_bytes = generate_audio("Logan Link AI Online")
            await ctx.send(file=discord.File(audio_bytes, "activation.mp3"))
            await play_audio(ctx, audio_bytes)
            await ctx.send("Voice activation successful. Connected to voice channel.")
        else:
            await ctx.send("You need to be in a voice channel to activate voice features.")
    except Exception as e:
        await ctx.send(f"Error during voice activation: {str(e)}")

@loganlink.command()
async def deactivate(ctx):
    """Disconnects the bot from voice channel"""
    global is_voice_active, voice_client
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        is_voice_active = False
        await ctx.send("Voice deactivated and disconnected from voice channel.")
    else:
        await ctx.send("I'm not currently in a voice channel.")

@loganlink.command()
async def say(ctx, *, text):
    """Generates audio from text and sends it (plays in voice if activated)"""
    try:
        async with ctx.typing():
            audio_bytes = generate_audio(text)
            await ctx.send(f"📝 Text: {text}")
            await ctx.send(file=discord.File(audio_bytes, "speech.mp3"))
            if is_voice_active:
                await play_audio(ctx, audio_bytes)
            else:
                await ctx.send("Note: Voice playback is not active. Use !loganlink activate to enable voice channel features.")
    except Exception as e:
        await ctx.send(f"Error generating audio: {str(e)}")

@loganlink.command()
async def talk(ctx, *, question):
    """Chat with the AI using text and voice (if activated)"""
    try:
        async with ctx.typing():
            messages = [
                {"role": "system", "content": "You are a Logan, a discord user who lives most of their life playing video games and getting high.  You may have a short temper if you are offended. Answer as Logan would."},
                {"role": "user", "content": question}
            ]
            response = openai_client.chat.completions.create(
                model=MODEL_ID,
                messages=messages
            )
            ai_response = response.choices[0].message.content
            audio_bytes = generate_audio(ai_response)
            await ctx.send(ai_response)
            await ctx.send(file=discord.File(audio_bytes, "response.mp3"))
            if is_voice_active:
                await play_audio(ctx, audio_bytes)
            else:
                await ctx.send("Note: Voice playback is not active. Use !loganlink activate to enable voice channel features.")
    except Exception as e:
        await ctx.send(f"Error processing question: {str(e)}")

@loganlink.command()
async def chat(ctx, *, message):
    """Chat with the AI using text only"""
    try:
        async with ctx.typing():
            messages = [
                {"role": "system", "content": "You are a Logan, a discord user who lives most of their life playing video games and getting high.  You may have a short temper if you are offended. Answer as Logan would."},
                {"role": "user", "content": message}
            ]
            response = openai_client.chat.completions.create(
                model=MODEL_ID,
                messages=messages
            )
            ai_response = response.choices[0].message.content
            await ctx.send(ai_response)
    except Exception as e:
        await ctx.send(f"Error during chat: {str(e)}")

@loganlink.command()
async def repeat(ctx):
    """Converts an uploaded audio file to speech using the bot's voice"""
    try:
        if not ctx.message.attachments:
            await ctx.send("Please attach an audio file (MP3) with your command!")
            return
        attachment = ctx.message.attachments[0]
        if not attachment.filename.lower().endswith('.mp3'):
            await ctx.send("Please provide an MP3 file!")
            return
        async with ctx.typing():
            audio_data = await attachment.read()
            input_file = io.BytesIO(audio_data)
            try:
                audio_stream = elevenlabs_client.speech_to_speech.convert_as_stream(
                    voice_id=VOICE_ID,
                    audio=input_file,
                    output_format="mp3_44100_128",
                    model_id="eleven_multilingual_sts_v2"
                )
                audio_bytes = io.BytesIO()
                for chunk in audio_stream:
                    audio_bytes.write(chunk)
                audio_bytes.seek(0)
                await ctx.send("Here's your audio repeated in my voice:")
                await ctx.send(file=discord.File(audio_bytes, "repeated_audio.mp3"))
                if is_voice_active:
                    await play_audio(ctx, audio_bytes)
                else:
                    await ctx.send("Note: Voice playback is not active. Use !loganlink activate to enable voice channel features.")
            except Exception as e:
                await ctx.send(f"Error converting audio: {str(e)}")
    except Exception as e:
        await ctx.send(f"Error processing audio: {str(e)}")

# Run the bot
bot.run(os.getenv('DISCORD_BOT_TOKEN'))
