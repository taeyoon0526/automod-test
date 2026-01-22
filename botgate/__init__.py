from .botgate import BotGate


async def setup(bot):
    await bot.add_cog(BotGate(bot))
