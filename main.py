import discord
from discord import app_commands
from discord.ext import commands
import os
from dotenv import load_dotenv
from openai import OpenAI
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("discord.bot")

# Load environment variables
load_dotenv()


class SummaryBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True

        super().__init__(command_prefix="!", intents=intents, help_command=None)

        self.required_role_id = int(os.getenv("REQUIRED_ROLE_ID"))
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def setup_hook(self):
        await self.tree.sync()
        logger.info("Commands synced globally")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(
            f"Invite URL: https://discord.com/api/oauth2/authorize?client_id={self.user.id}&permissions=277025770560&scope=bot%20applications.commands"
        )


bot = SummaryBot()


@bot.tree.command(
    name="summarize", description="Summarize a channel's messages using AI"
)
@app_commands.describe(
    channel="The channel to summarize",
    message_count="Number of messages to analyze (1-200)",
)
async def summarize(
    interaction: discord.Interaction, channel: discord.TextChannel, message_count: int
):
    logger.debug(f"Command invoked by {interaction.user} in {channel.guild.name}")

    # Check permissions
    if not any(role.id == bot.required_role_id for role in interaction.user.roles):
        logger.warning(f"Permission denied for {interaction.user}")
        return await interaction.response.send_message(
            "⛔ You don't have permission to use this command!", ephemeral=True
        )

    # Validate input
    if not 1 <= message_count <= 200:
        return await interaction.response.send_message(
            "❌ Please choose a number between 1 and 200", ephemeral=True
        )

    await interaction.response.defer()

    try:
        # Fetch messages
        logger.info(f"Fetching {message_count} messages from #{channel.name}")
        messages = [
            message
            async for message in channel.history(limit=message_count)
            if message.content
        ]

        if not messages:
            return await interaction.followup.send(
                "❌ No messages found in this channel!"
            )

        # Prepare conversation history
        conversation = "\n".join(
            [
                f"{message.author.display_name}: {message.content}"
                for message in reversed(messages)
            ]
        )

        # Generate summary
        logger.info("Generating AI summary...")
        response = bot.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional conversation analyst. Create a detailed summary of this Discord conversation.",
                },
                {
                    "role": "user",
                    "content": f"Analyze this conversation and provide a comprehensive summary:\n\n{conversation}",
                },
            ],
            temperature=0.5,
            max_tokens=2000,
        )

        summary = response.choices[0].message.content

        # Create and send embed
        embed = discord.Embed(
            title=f"📝 Summary of #{channel.name}",
            description=summary,
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Messages Analyzed", value=len(messages))
        embed.add_field(
            name="Time Range",
            value=f"{messages[-1].created_at.strftime('%Y-%m-%d %H:%M')} - {messages[0].created_at.strftime('%Y-%m-%d %H:%M')}",
        )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        await interaction.followup.send(f"❌ Failed to generate summary: {str(e)}")


if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
