import discord
from discord import app_commands
from discord.ext import commands
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Configuration
REQUIRED_ROLE_ID = int(os.getenv("REQUIRED_ROLE_ID"))
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(e)


def format_messages(messages):
    return "\n".join(
        [f"{message.author.display_name}: {message.content}"
         for message in reversed(messages) if message.content]
    )


async def generate_ai_summary(messages):
    conversation = format_messages(messages)

    response = openai_client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system",
             "content": "You are a Discord conversation analyst. Create a structured summary including key points, participants, and notable messages."},
            {"role": "user",
             "content": f"Analyze this conversation:\n{conversation}\n\nProvide a comprehensive summary with markdown formatting."}
        ],
        temperature=0.7,
        max_tokens=1500
    )
    return response.choices[0].message.content


@bot.tree.command(name="summarize", description="Summarize channel messages using AI")
@app_commands.describe(
    channel="The channel to summarize",
    message_count="Number of messages to analyze (1-200)"
)
async def summarize(interaction: discord.Interaction, channel: discord.TextChannel, message_count: int):
    # Check role permission
    if not any(role.id == REQUIRED_ROLE_ID for role in interaction.user.roles):
        return await interaction.response.send_message(
            "⛔ You don't have permission to use this command!",
            ephemeral=True
        )

    # Validate message count
    if not 1 <= message_count <= 200:
        return await interaction.response.send_message(
            "❌ Please choose a number between 1 and 200",
            ephemeral=True
        )

    await interaction.response.defer()

    try:
        # Fetch messages
        messages = [message async for message in channel.history(limit=message_count) if message.content]
        if not messages:
            return await interaction.followup.send("❌ No messages found in this channel!")

        # Generate summary
        summary = await generate_ai_summary(messages)

        # Create embed
        embed = discord.Embed(
            title=f"📝 Summary of #{channel.name}",
            description=summary,
            color=0x00ff00
        )
        embed.set_footer(text=f"Analyzed {len(messages)} messages")

        await interaction.followup.send(embed=embed)

    except discord.Forbidden:
        await interaction.followup.send("🔒 Missing permissions to read that channel!")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)